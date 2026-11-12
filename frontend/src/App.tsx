import { Layout } from './components/Layout';
import { IconSprite } from './components/Icon';
import { useRoute } from './router';
import Home from './pages/Home';
import Results from './pages/Results';
import Watch from './pages/Watch';
import Guide from './pages/Guide';

export default function App() {
  const route = useRoute();
  const t = route.params.get('t');

  let page;
  switch (route.path) {
    case '/results':
      page = <Results query={route.params.get('q') || '기초연금 신청서 어떻게 써요?'} />;
      break;
    case '/watch':
      page = <Watch videoId={route.id || 'v1'} startAt={t ? Number(t) : undefined} />;
      break;
    case '/guide':
      page = <Guide />;
      break;
    default:
      page = <Home />;
  }

  return (
    <>
      <IconSprite />
      <Layout current={route.path}>{page}</Layout>
    </>
  );
}
