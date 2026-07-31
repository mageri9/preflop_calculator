interface TelegramWebApp {
  initData: string;
  initDataUnsafe: any;
  ready: () => void;
  expand: () => void;
  close: () => void;
  MainButton: {
    text: string;
    show: () => void;
    hide: () => void;
    onClick: (fn: () => void) => void;
  };
  colorScheme: 'light' | 'dark';
}

interface Window {
  Telegram?: {
    WebApp?: TelegramWebApp;
  };
}
