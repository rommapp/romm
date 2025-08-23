export type InputAction =
  | 'moveUp'
  | 'moveDown'
  | 'moveLeft'
  | 'moveRight'
  | 'confirm'
  | 'back'
  | 'menu'
  | 'tabNext'
  | 'tabPrev'
  | 'toggleFavorite';

export type InputListener = (action: InputAction) => boolean | void;
