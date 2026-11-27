export async function openLocalRoom(value, {openTab, release, navigate}) {
  const port = String(value).trim();
  if (!/^\d{1,5}$/.test(port) || Number(port) < 1 || Number(port) > 65535) {
    throw Error('小屋端口应为 1 至 65535 之间的整数。');
  }
  const url = 'http://127.0.0.1:' + Number(port) + '/passport';
  // Reserve the tab during the button gesture, before USB cleanup can yield.
  const tab = openTab();
  if (tab) tab.opener = null;
  try {
    await release();
    if (tab && !tab.closed) tab.location.replace(url);
    else navigate(url);
  } catch (error) {
    tab?.close();
    throw error;
  }
}
