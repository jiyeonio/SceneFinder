import { useEffect, useState } from 'react';

// 간단한 해시 라우터: #/ , #/results?q=..., #/watch/v1, #/guide
export interface Route {
  path: string;
  params: URLSearchParams;
  id?: string;
}

function read(): Route {
  const raw = window.location.hash.replace(/^#/, '') || '/';
  const [pathPart, query = ''] = raw.split('?');
  const segs = pathPart.split('/').filter(Boolean);
  return { path: '/' + (segs[0] ?? ''), id: segs[1], params: new URLSearchParams(query) };
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(read);
  useEffect(() => {
    const on = () => {
      setRoute(read());
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return route;
}

export function go(to: string) {
  window.location.hash = to;
}
