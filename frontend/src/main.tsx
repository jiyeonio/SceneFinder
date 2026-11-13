import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/base.css';
import './styles/theme.css';
import App from './App';
// 최종 디자인 스타일은 페이지 CSS 다음에 불러와야 해요 (순서 바꾸지 마세요)
import './styles/theme-final.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
