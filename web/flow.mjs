export const SIZE = 8 * 1024 * 1024;

export async function sha(bytes) {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
}

export async function backupName(board, bytes) {
  return 'passport-' + board + '-' + await sha(bytes) + '.bin';
}

export async function install(io, app, manifest) {
  if (app.length !== SIZE || manifest.size !== SIZE || await sha(app) !== manifest.sha256)
    throw Error('公开安装包校验失败。请刷新页面重新连接。');
  const original = await io.read();
  if (original.length !== SIZE) throw Error('挂件备份不完整。');
  const saved = await io.save(original);
  if (saved.length !== SIZE || await sha(saved) !== await sha(original))
    throw Error('电脑上的备份校验失败，安装已停止。');
  await io.write(app);
}

export async function restore(io, file, name) {
  if (file.length !== SIZE || name !== await backupName(io.board, file))
    throw Error('文件与这台挂件或原始校验值不符，请选择安装时保存的原名备份。');
  await io.write(file);
}
