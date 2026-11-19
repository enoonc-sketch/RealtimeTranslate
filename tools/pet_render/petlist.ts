// 宠物列表（与 ../../pet_catalog.py 保持一致：想加新宠物，两边各加一行 + pets3d.ts 的 SPEC 里加造型）
export interface PetInfo { id: string; name: string; emoji: string }
export const PETS: PetInfo[] = [
  { id: 'cat', name: '猫咪', emoji: '🐱' }, { id: 'dog', name: '小狗', emoji: '🐶' }, { id: 'bunny', name: '兔兔', emoji: '🐰' },
  { id: 'bear', name: '小熊', emoji: '🐻' }, { id: 'panda', name: '熊猫', emoji: '🐼' }, { id: 'fox', name: '狐狸', emoji: '🦊' },
  { id: 'tiger', name: '小老虎', emoji: '🐯' }, { id: 'pig', name: '小猪', emoji: '🐷' }, { id: 'hamster', name: '仓鼠', emoji: '🐹' },
  { id: 'chick', name: '小鸡', emoji: '🐥' }, { id: 'duck', name: '小鸭', emoji: '🦆' }, { id: 'penguin', name: '企鹅', emoji: '🐧' },
  { id: 'frog', name: '青蛙', emoji: '🐸' }, { id: 'dino', name: '小恐龙', emoji: '🦖' }, { id: 'unicorn', name: '独角兽', emoji: '🦄' },
  { id: 'slime', name: '史莱姆', emoji: '🟢' }, { id: 'ghost', name: '小幽灵', emoji: '👻' }, { id: 'robot', name: '机器人', emoji: '🤖' }
];
