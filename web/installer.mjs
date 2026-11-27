import {ESPLoader, Transport} from 'esptool-js';
import SparkMD5 from 'spark-md5';
import {SIZE, install, restore, backupName} from './flow.mjs';
import {openLocalRoom} from './pairing.mjs';

const el = id => document.getElementById(id);
let loader, transport, original, board, suggestedName, busy = false;
const canInstall = Boolean(navigator.serial && window.showSaveFilePicker && window.isSecureContext);
function progress(text, value) {
  el('status').textContent = text;
  el('progress').hidden = value === undefined;
  if (value !== undefined) el('progress').value = value;
}
async function closePort(requireRelease = false) {
  if (loader?.IS_STUB) try { await loader.after('hard_reset'); } catch (error) { if (requireRelease) throw error; }
  if (transport) try { await transport.disconnect(); } catch (error) { if (requireRelease) throw error; }
  loader = transport = original = board = suggestedName = null;
}
function controls() {
  el('connect').hidden = !!board;
  el('install').hidden = !board;
  el('restore').hidden = !board;
  el('disconnect').hidden = !board;
  for (const button of document.querySelectorAll('button')) button.disabled = busy;
  el('connect').disabled = busy || !canInstall;
}
async function action(fn) {
  if (busy) return;
  busy = true; controls();
  try { await fn(); }
  catch (error) {
    await closePort();
    const cancelled = ['NotFoundError','AbortError'].includes(error.name);
    progress(cancelled ? '已取消，请在准备好后重新连接。' :
      '操作未完成。' + error.message + ' 请检查数据线，关闭占用串口的其他程序，再重新连接。');
  } finally { busy = false; controls(); }
}
async function connect() {
  const port = await navigator.serial.requestPort({filters:[{usbVendorId:0x303a,usbProductId:0x1001}]});
  progress('正在识别挂件…');
  transport = new Transport(port, false);
  loader = new ESPLoader({transport, baudrate:460800, terminal:{clean(){},writeLine(){},write(){}}});
  await loader.main();
  if (loader.chip.CHIP_NAME !== 'ESP32-C3' || await loader.getFlashSize() !== 8192)
    throw Error('此版本需要 ESP32-C3、8 MB 的 AI Passport。');
  board = (await loader.chip.readMac(loader)).replaceAll(':','').toLowerCase();
  original = new Uint8Array(SIZE);
  const block = 256 * 1024;
  for (let offset=0; offset<SIZE; offset+=block) {
    progress('正在读取原机备份，请保持连接…',offset/SIZE);
    const bytes=await loader.readFlash(offset,block);
    if(bytes.length!==block) throw Error('挂件读取中断。');
    // The Espressif stub sends a final MD5 frame after readFlash's last ACK.
    const {value: digest} = await transport.read(loader.FLASH_READ_TIMEOUT).next();
    if (!(digest instanceof Uint8Array) || digest.length !== 16 ||
        loader.toHex(digest).toLowerCase() !== SparkMD5.ArrayBuffer.hash(bytes.buffer))
      throw Error('本段备份校验失败，挂件尚未写入。');
    original.set(bytes,offset);
  }
  if (SparkMD5.ArrayBuffer.hash(original.buffer) !== (await loader.flashMd5sum(0,SIZE)).toLowerCase())
    throw Error('备份与设备内容不一致。');
  suggestedName = await backupName(board,original);
  progress('已读出原机内容。请保存备份，再安装灵宠屋。');
}
async function write(bytes) {
  const chunkSize=512*1024;
  const files=[];
  for (let offset=0;offset<SIZE;offset+=chunkSize) {
    const slice=bytes.subarray(offset,offset+chunkSize);
    const strings=[];
    for (let i=0;i<slice.length;i+=8192) strings.push(String.fromCharCode(...slice.subarray(i,i+8192)));
    files.push({address:offset,data:strings.join('')});
  }
  await loader.writeFlash({fileArray:files, flashSize:'keep',flashMode:'keep',flashFreq:'keep',
    eraseAll:false,compress:true,calculateMD5Hash:s=>SparkMD5.hashBinary(s),
    reportProgress:(index,n,total)=>progress('正在写入并校验，请保持连接…',(index+n/total)/files.length)});
}
el('pair').onclick = async () => {
  if (busy) return;
  busy = true;
  controls();
  try {
    await openLocalRoom(el('room-port').value, {
      openTab: () => window.open('about:blank', '_blank'),
      release: () => closePort(true),
      navigate(url) {
        busy = false;
        window.location.assign(url);
      }
    });
    el('pair-status').textContent = '已打开本机配对页。如果提示无法访问，请先启动电脑上的灵宠屋；如果显示“找不到页面”或 404，请先更新灵宠屋。';
  } catch (error) {
    el('pair-status').textContent = error.message + ' 请检查小屋端口或重新插拔挂件后再试。';
  } finally {
    busy = false;
    controls();
  }
};
el('connect').onclick=()=>action(connect);
el('disconnect').onclick=()=>action(async()=>{await closePort();progress('已断开。');});
el('install').onclick=()=>action(async()=>{
  const handle=await window.showSaveFilePicker({suggestedName,types:[{description:'原机备份',accept:{'application/octet-stream':['.bin']}}]});
  if (handle.name !== suggestedName) throw Error('请保留备份的默认文件名，以便日后恢复。');
  progress('正在下载并核对公开安装包…');
  const [r,m]=await Promise.all([fetch('./passport.bin?v=0.2.0'),fetch('./image.json',{cache:'no-cache'})]);
  if (!r.ok || !m.ok) throw Error('安装包暂时无法下载。');
  await install({read:async()=>original,save:async b=>{
    const stream=await handle.createWritable(); await stream.write(b); await stream.close();
    return new Uint8Array(await (await handle.getFile()).arrayBuffer());
  },write},new Uint8Array(await r.arrayBuffer()),await m.json());
  await closePort();progress('写入和校验完成。在挂件上用 ▲ / ▼ 选伙伴，按 OK 确认。');
});
el('restore').onclick=()=>action(async()=>{
  const [handle]=await window.showOpenFilePicker({multiple:false,types:[{description:'原机备份',accept:{'application/octet-stream':['.bin']}}]});
  const file=await handle.getFile();
  if (file.size!==SIZE) throw Error('不是完整的 8 MB 备份。');
  if (!confirm('将恢复保存备份那一刻的全部内容，并覆盖现在的挂件。继续吗？')) return;
  await restore({board,write},new Uint8Array(await file.arrayBuffer()),file.name);
  await closePort();progress('原机备份已恢复，校验完成。');
});
window.addEventListener('beforeunload',event=>{if(busy||board){event.preventDefault();event.returnValue='';}});
if (!canInstall) {
  el('connect').disabled=true;
  progress('请在电脑上用 Chrome 或 Edge 打开此页，并允许选择 USB 设备和保存备份。');
}
