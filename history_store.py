"""翻译记录存储 — 只用标准库 sqlite3，不装任何第三方库。

存什么：每次翻译成功的 原文 / 译文 / 语言 / 引擎 / 来源（主窗口、指针取词、悬停取词、截图），
可以收藏、搜索、导出（CSV / TXT / JSON），也可以当「翻译记忆」用：相同原文 + 相同语言
直接取已存译文，不再联网。

设计要点：
- 相同的（原文, 请求的源语言, 请求的目标语言）只存一条：再次翻译只更新译文 / 时间 / 次数，
  不会越堆越多，收藏状态保留。
- 超过上限时只删最旧的「未收藏」记录，收藏永远不会被自动清掉。
- 线程安全：每次操作单独开连接，外加一把锁（气泡翻译在工作线程里写，界面在主线程里读）。
- 存储出任何问题（磁盘满、文件被占用、数据库损坏）都不抛异常、不影响翻译：add 返回 None，
  查询返回空。只有导出会把 OSError 抛给界面，让界面告诉用户。

非 Windows 上同样能用（测试在 Linux 上跑）。
"""

import csv
import json
import os
import sqlite3
import threading
import time
from contextlib import closing

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL    NOT NULL,
    src     TEXT    NOT NULL,
    dst     TEXT    NOT NULL,
    sl      TEXT    NOT NULL DEFAULT '',
    tl      TEXT    NOT NULL DEFAULT '',
    req_sl  TEXT    NOT NULL DEFAULT 'auto',
    req_tl  TEXT    NOT NULL DEFAULT '',
    engine  TEXT    NOT NULL DEFAULT '',
    kind    TEXT    NOT NULL DEFAULT 'main',
    fav     INTEGER NOT NULL DEFAULT 0,
    count   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_history_ts ON history(ts DESC);
CREATE INDEX IF NOT EXISTS idx_history_key ON history(req_tl, req_sl, src);
"""

KIND_NAMES = {"main": "主窗口", "pointer": "指针取词", "hover": "悬停取词",
              "screenshot": "截图翻译", "doc": "文档翻译", "image": "图片翻译",
              "replace": "翻译并替换"}
_COLS = ("id", "ts", "src", "dst", "sl", "tl", "req_sl", "req_tl", "engine", "kind", "fav", "count")


def _like(term):
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class HistoryStore:
    def __init__(self, path, max_items=2000):
        self.path = path
        self.max_items = max_items          # 未收藏记录的上限；收藏不计入、不会被清
        self._lock = threading.RLock()
        self._ready = False

    # ---- 内部 --------------------------------------------------------
    def _connect(self):
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        if not self._ready:
            conn.executescript(_SCHEMA)
            conn.commit()
            self._ready = True
        return conn

    @staticmethod
    def _row(r):
        return {k: r[k] for k in _COLS}

    # ---- 写 ----------------------------------------------------------
    def add(self, src, dst, sl="", tl="", engine="", kind="main",
            req_sl="auto", req_tl="", fav=False):
        """保存一条翻译；成功返回记录 id，失败 / 内容为空返回 None（绝不抛异常）。"""
        src, dst = (src or "").strip(), (dst or "").strip()
        if not src or not dst:
            return None
        req_tl = req_tl or tl
        try:
            with self._lock, closing(self._connect()) as c:
                row = c.execute(
                    "SELECT id FROM history WHERE src=? AND req_sl=? AND req_tl=?",
                    (src, req_sl, req_tl)).fetchone()
                now = time.time()
                if row:
                    c.execute(
                        "UPDATE history SET ts=?, dst=?, sl=?, tl=?, engine=?, kind=?, "
                        "count=count+1, fav=MAX(fav, ?) WHERE id=?",
                        (now, dst, sl, tl, engine, kind, 1 if fav else 0, row["id"]))
                    rid = row["id"]
                else:
                    cur = c.execute(
                        "INSERT INTO history (ts, src, dst, sl, tl, req_sl, req_tl, engine, kind, fav) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (now, src, dst, sl, tl, req_sl, req_tl, engine, kind, 1 if fav else 0))
                    rid = cur.lastrowid
                self._prune(c)
                c.commit()
                return rid
        except Exception:
            return None

    def _prune(self, c):
        try:
            n = int(self.max_items)
        except Exception:
            return
        if n <= 0:
            return
        c.execute(
            "DELETE FROM history WHERE fav=0 AND id NOT IN "
            "(SELECT id FROM history WHERE fav=0 ORDER BY ts DESC, id DESC LIMIT ?)", (n,))

    def set_fav(self, rid, fav=True):
        try:
            with self._lock, closing(self._connect()) as c:
                c.execute("UPDATE history SET fav=? WHERE id=?", (1 if fav else 0, int(rid)))
                c.commit()
                return True
        except Exception:
            return False

    def delete(self, ids):
        ids = [int(i) for i in ids]
        if not ids:
            return 0
        try:
            with self._lock, closing(self._connect()) as c:
                n = 0
                for i in range(0, len(ids), 500):
                    part = ids[i:i + 500]
                    n += c.execute("DELETE FROM history WHERE id IN (%s)" % ",".join("?" * len(part)),
                                   part).rowcount
                c.commit()
                return n
        except Exception:
            return 0

    def clear(self, keep_fav=True):
        """清空记录；默认保留收藏。返回删除条数。"""
        try:
            with self._lock, closing(self._connect()) as c:
                n = c.execute("DELETE FROM history" + (" WHERE fav=0" if keep_fav else "")).rowcount
                c.commit()
                return n
        except Exception:
            return 0

    # ---- 读 ----------------------------------------------------------
    def search(self, query="", fav_only=False, limit=1000):
        """按时间从新到旧；query 里空格分隔的每个词都要出现在原文或译文里。"""
        sql, args = "SELECT * FROM history WHERE 1=1", []
        for term in (query or "").split():
            sql += " AND (src LIKE ? ESCAPE '\\' OR dst LIKE ? ESCAPE '\\')"
            args += [_like(term), _like(term)]
        if fav_only:
            sql += " AND fav=1"
        sql += " ORDER BY ts DESC, id DESC"
        if limit:
            sql += " LIMIT %d" % int(limit)
        try:
            with self._lock, closing(self._connect()) as c:
                return [self._row(r) for r in c.execute(sql, args).fetchall()]
        except Exception:
            return []

    def get(self, rid):
        try:
            with self._lock, closing(self._connect()) as c:
                r = c.execute("SELECT * FROM history WHERE id=?", (int(rid),)).fetchone()
                return self._row(r) if r else None
        except Exception:
            return None

    def find(self, src, req_sl="auto", req_tl=""):
        """按（原文, 请求的源语言, 请求的目标语言）精确找一条；没有返回 None。

        源语言选「自动检测」时不限定源语言（旧记录用什么源语言存的都行）。
        """
        src = (src or "").strip()
        if not src:
            return None
        sql, args = "SELECT * FROM history WHERE src=? AND req_tl=?", [src, req_tl]
        if req_sl and req_sl != "auto":
            sql += " AND req_sl=?"
            args.append(req_sl)
        sql += " ORDER BY ts DESC LIMIT 1"
        try:
            with self._lock, closing(self._connect()) as c:
                r = c.execute(sql, args).fetchone()
                return self._row(r) if r else None
        except Exception:
            return None

    def lookup(self, src, req_sl="auto", req_tl=""):
        """翻译记忆：相同原文 + 相同语言，返回已存译文；没有返回 None。"""
        r = self.find(src, req_sl, req_tl)
        return r["dst"] if r else None

    def count(self, fav_only=False):
        try:
            with self._lock, closing(self._connect()) as c:
                return c.execute("SELECT COUNT(*) FROM history" + (" WHERE fav=1" if fav_only else "")
                                 ).fetchone()[0]
        except Exception:
            return 0

    # ---- 导出 --------------------------------------------------------
    def export(self, path, rows=None):
        """导出到 .csv / .txt / .json（按扩展名；其他当 .txt）。rows 为空 = 全部记录。
        写文件失败抛 OSError，由界面提示用户。返回导出条数。"""
        if rows is None:
            rows = self.search("", False, 0)
        ext = os.path.splitext(path)[1].lower()
        stamp = lambda ts: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        if ext == ".json":
            data = [{"time": stamp(r["ts"]), "source": r["src"], "translation": r["dst"],
                     "from": r["sl"], "to": r["tl"], "engine": r["engine"],
                     "via": KIND_NAMES.get(r["kind"], r["kind"]), "favorite": bool(r["fav"]),
                     "count": r["count"]} for r in rows]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        elif ext == ".csv":
            # utf-8-sig：Excel 双击打开中文不乱码
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["时间", "原文", "译文", "源语言", "目标语言", "引擎", "来源", "收藏", "次数"])
                for r in rows:
                    w.writerow([stamp(r["ts"]), r["src"], r["dst"], r["sl"], r["tl"], r["engine"],
                                KIND_NAMES.get(r["kind"], r["kind"]), "★" if r["fav"] else "", r["count"]])
        else:
            with open(path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write("[%s] %s → %s · %s%s\n" % (
                        stamp(r["ts"]), r["sl"] or "?", r["tl"] or "?", r["engine"],
                        "  ★" if r["fav"] else ""))
                    f.write("%s\n%s\n\n" % (r["src"], r["dst"]))
        return len(rows)
