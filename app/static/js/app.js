// GCS Portal Frontend Application
let currentPath = '';
let currentFolders = [];
let currentFiles = [];
let uploadQueue = [];
let deleteTargetPath = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  const urlParams = new URLSearchParams(window.location.search);
  const initialPath = urlParams.get('prefix') || '';
  navigateTo(initialPath);
  setupDropZone();
});

// Update URL without page reload
function updateBrowserUrl(path) {
  const url = new URL(window.location);
  if (path) {
    url.searchParams.set('prefix', path);
  } else {
    url.searchParams.delete('prefix');
  }
  window.history.pushState({ path }, '', url);
}

// Handle browser Back/Forward navigation
window.addEventListener('popstate', (event) => {
  const path = event.state && event.state.path ? event.state.path : '';
  navigateTo(path, false);
});

// Navigate to folder
async function navigateTo(path, updateHistory = true) {
  currentPath = path ? path.replace(/^\/+/, '') : '';
  if (currentPath && !currentPath.endsWith('/')) {
    currentPath += '/';
  }

  if (updateHistory) {
    updateBrowserUrl(currentPath);
  }

  const container = document.getElementById('file-list-container');
  container.innerHTML = `
    <div class="py-20 flex flex-col items-center justify-center text-slate-400 space-y-3">
      <i data-lucide="loader-2" class="w-8 h-8 animate-spin text-blue-500"></i>
      <span class="text-sm">Loading folder contents...</span>
    </div>
  `;
  if (window.lucide) lucide.createIcons();

  try {
    const res = await fetch(`/api/files?prefix=${encodeURIComponent(currentPath)}`);
    if (res.status === 401) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
      return;
    }
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to list files');
    }

    const data = await res.json();
    currentFolders = data.folders || [];
    currentFiles = data.files || [];

    renderBreadcrumbs(data.breadcrumbs || []);
    renderList(currentFolders, currentFiles);
    updateStats(data);

    // Reset filter input
    const filterInput = document.getElementById('filter-input');
    if (filterInput) filterInput.value = '';

  } catch (error) {
    container.innerHTML = `
      <div class="py-16 text-center text-rose-500 space-y-2">
        <i data-lucide="alert-circle" class="w-8 h-8 mx-auto"></i>
        <p class="font-medium text-sm">Error loading directory: ${error.message}</p>
        <button onclick="navigateTo('${currentPath}')" class="px-3 py-1 bg-white border border-slate-300 text-slate-700 rounded text-xs hover:bg-slate-50">Retry</button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    showToast(error.message, 'error');
  }
}

// Refresh current directory
function refreshCurrentFolder() {
  const icon = document.getElementById('refresh-icon');
  if (icon) icon.classList.add('animate-spin');
  navigateTo(currentPath).finally(() => {
    if (icon) icon.classList.remove('animate-spin');
  });
}

// Render breadcrumb navigation bar
function renderBreadcrumbs(breadcrumbs) {
  const bar = document.getElementById('breadcrumb-bar');
  if (!bar) return;

  bar.innerHTML = '';
  breadcrumbs.forEach((crumb, index) => {
    if (index > 0) {
      const sep = document.createElement('span');
      sep.className = 'text-slate-400 mx-1 flex items-center';
      sep.innerHTML = '<i data-lucide="chevron-right" class="w-3.5 h-3.5"></i>';
      bar.appendChild(sep);
    }

    const btn = document.createElement('button');
    btn.className = `flex items-center px-1.5 py-0.5 rounded transition ${
      index === breadcrumbs.length - 1
        ? 'font-bold text-slate-900 bg-slate-100'
        : 'hover:text-blue-600 hover:bg-slate-100 text-slate-600'
    }`;
    btn.onclick = () => navigateTo(crumb.path);

    if (index === 0) {
      btn.innerHTML = '<i data-lucide="hard-drive" class="w-3.5 h-3.5 mr-1 text-blue-500"></i><span>root</span>';
    } else {
      btn.innerText = crumb.name;
    }
    bar.appendChild(btn);
  });

  if (window.lucide) lucide.createIcons();
}

// Update summary stats
function updateStats(data) {
  const folderCount = document.getElementById('folder-count');
  const fileCount = document.getElementById('file-count');
  const folderSize = document.getElementById('folder-size');

  if (folderCount) folderCount.innerText = `${data.folders.length} Folders`;
  if (fileCount) fileCount.innerText = `${data.files.length} Files`;
  if (folderSize) folderSize.innerText = data.total_size_formatted || '0 B';
}

// File icon selector based on extension
function getFileIcon(filename) {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.nc') || lower.endsWith('.nc4') || lower.endsWith('.grb') || lower.endsWith('.grib2')) {
    return { icon: 'cloud-rain', color: 'text-sky-600 bg-sky-50' };
  }
  if (lower.endsWith('.zarr')) {
    return { icon: 'layers', color: 'text-indigo-600 bg-indigo-50' };
  }
  if (lower.endsWith('.csv') || lower.endsWith('.tsv') || lower.endsWith('.xlsx')) {
    return { icon: 'table', color: 'text-emerald-600 bg-emerald-50' };
  }
  if (lower.endsWith('.json') || lower.endsWith('.yaml') || lower.endsWith('.yml') || lower.endsWith('.xml')) {
    return { icon: 'file-code', color: 'text-amber-600 bg-amber-50' };
  }
  if (lower.endsWith('.txt') || lower.endsWith('.log') || lower.endsWith('.md')) {
    return { icon: 'file-text', color: 'text-slate-600 bg-slate-100' };
  }
  if (lower.endsWith('.png') || lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.gif') || lower.endsWith('.svg')) {
    return { icon: 'image', color: 'text-purple-600 bg-purple-50' };
  }
  if (lower.endsWith('.tar') || lower.endsWith('.gz') || lower.endsWith('.zip') || lower.endsWith('.tgz')) {
    return { icon: 'archive', color: 'text-orange-600 bg-orange-50' };
  }
  return { icon: 'file', color: 'text-slate-600 bg-slate-100' };
}

// Format ISO date
function formatDate(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return isoStr;
  }
}

// Render file and folder list
function renderList(folders, files) {
  const container = document.getElementById('file-list-container');
  if (!container) return;

  if (folders.length === 0 && files.length === 0) {
    container.innerHTML = `
      <div class="py-20 text-center text-slate-400 space-y-3">
        <div class="w-16 h-16 mx-auto rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
          <i data-lucide="folder-open" class="w-8 h-8"></i>
        </div>
        <p class="text-sm font-medium text-slate-600">This directory is empty</p>
        <p class="text-xs text-slate-400">Upload files or create a subfolder to get started</p>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  let html = '';

  // Render Folders
  folders.forEach((folder) => {
    html += `
      <div class="grid grid-cols-12 gap-3 px-6 py-3 items-center hover:bg-slate-50/80 transition group border-b border-slate-100">
        <div class="col-span-6 sm:col-span-5 flex items-center space-x-3 cursor-pointer min-w-0" onclick="navigateTo('${folder.full_path}')">
          <div class="w-8 h-8 rounded-lg bg-amber-50 text-amber-500 flex items-center justify-center flex-shrink-0 group-hover:scale-105 transition">
            <i data-lucide="folder" class="w-4 h-4 fill-amber-500"></i>
          </div>
          <span class="font-medium text-sm text-slate-800 hover:text-blue-600 truncate">${escapeHtml(folder.name)}</span>
        </div>
        <div class="col-span-2 hidden sm:block text-right text-xs text-slate-400 font-mono">Folder</div>
        <div class="col-span-3 hidden md:block text-xs text-slate-400">—</div>
        <div class="col-span-6 sm:col-span-5 md:col-span-2 flex items-center justify-end space-x-1">
          <button onclick="navigateTo('${folder.full_path}')" title="Open Folder"
            class="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition">
            <i data-lucide="folder-open" class="w-4 h-4"></i>
          </button>
          <button onclick="promptDelete('${folder.full_path}')" title="Delete Folder"
            class="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>
      </div>
    `;
  });

  // Render Files
  files.forEach((file) => {
    const iconMeta = getFileIcon(file.name);
    const isPreviewable = isFilePreviewable(file.name);

    html += `
      <div class="grid grid-cols-12 gap-3 px-6 py-3 items-center hover:bg-slate-50/80 transition group border-b border-slate-100">
        <div class="col-span-6 sm:col-span-5 flex items-center space-x-3 min-w-0">
          <div class="w-8 h-8 rounded-lg ${iconMeta.color} flex items-center justify-center flex-shrink-0">
            <i data-lucide="${iconMeta.icon}" class="w-4 h-4"></i>
          </div>
          <span class="font-medium text-sm text-slate-800 truncate" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
        </div>
        <div class="col-span-2 hidden sm:block text-right text-xs text-slate-600 font-mono font-medium">${file.size_formatted}</div>
        <div class="col-span-3 hidden md:block text-xs text-slate-500">${formatDate(file.updated)}</div>
        <div class="col-span-6 sm:col-span-5 md:col-span-2 flex items-center justify-end space-x-1">
          <button onclick="downloadFile('${file.full_path}')" title="Direct Download"
            class="p-1.5 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition">
            <i data-lucide="download" class="w-4 h-4"></i>
          </button>
          <button onclick="copySignedUrl('${file.full_path}')" title="Copy Signed Link (1h)"
            class="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition">
            <i data-lucide="link-2" class="w-4 h-4"></i>
          </button>
          ${isPreviewable ? `
          <button onclick="previewFile('${file.full_path}')" title="Preview File"
            class="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition">
            <i data-lucide="eye" class="w-4 h-4"></i>
          </button>
          ` : ''}
          <button onclick="promptDelete('${file.full_path}')" title="Delete File"
            class="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

// Client-side search / filter
function applyFilter(query) {
  const q = query.trim().toLowerCase();
  if (!q) {
    renderList(currentFolders, currentFiles);
    return;
  }

  const filteredFolders = currentFolders.filter(f => f.name.toLowerCase().includes(q));
  const filteredFiles = currentFiles.filter(f => f.name.toLowerCase().includes(q));
  renderList(filteredFolders, filteredFiles);
}

// Check if file is readable for text preview
function isFilePreviewable(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  return ['txt', 'log', 'json', 'yaml', 'yml', 'csv', 'tsv', 'xml', 'md', 'sh', 'py'].includes(ext);
}

// Escape HTML for XSS prevention
function escapeHtml(str) {
  return str.replace(/[&<>'"]/g, 
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}

// ================= DOWNLOAD HANDLERS =================

// Trigger direct download via Signed URL
async function downloadFile(path) {
  try {
    showToast('Generating secure download link...', 'info');
    const res = await fetch(`/api/download-url?path=${encodeURIComponent(path)}`);
    if (!res.ok) {
      throw new Error('Failed to get download URL');
    }
    const data = await res.json();
    
    // Create temporary link and click it
    const a = document.createElement('a');
    a.href = data.signed_url;
    a.download = data.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
    showToast(`Downloading ${data.filename}`, 'success');
  } catch (error) {
    // Fallback to streaming download through backend
    window.location.href = `/api/stream-download?path=${encodeURIComponent(path)}`;
    showToast('Starting proxy download...', 'info');
  }
}

// Copy signed download link to clipboard
async function copySignedUrl(path) {
  try {
    const res = await fetch(`/api/download-url?path=${encodeURIComponent(path)}`);
    if (!res.ok) throw new Error('Could not generate link');
    const data = await res.json();
    await navigator.clipboard.writeText(data.signed_url);
    showToast('Direct signed link copied to clipboard (valid 1 hour)', 'success');
  } catch (err) {
    showToast('Failed to copy link: ' + err.message, 'error');
  }
}

// ================= UPLOAD MODAL & LOGIC =================

function openUploadModal() {
  const modal = document.getElementById('upload-modal');
  const targetLabel = document.getElementById('upload-target-path');
  if (targetLabel) targetLabel.innerText = currentPath ? currentPath : 'root';
  modal.classList.remove('hidden');
  clearUploadQueue();
}

function closeUploadModal() {
  const modal = document.getElementById('upload-modal');
  modal.classList.add('hidden');
}

function setupDropZone() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  if (!dropZone || !fileInput) return;

  dropZone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('dragover');
    }, false);
  });

  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFilesSelected(files);
  });

  fileInput.addEventListener('change', (e) => {
    handleFilesSelected(e.target.files);
  });
}

function handleFilesSelected(files) {
  if (!files || files.length === 0) return;

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    uploadQueue.push({
      file,
      targetPath: currentPath + file.name,
      progress: 0,
      status: 'pending', // 'pending', 'uploading', 'completed', 'error'
      error: null
    });
  }

  renderUploadQueue();
}

function clearUploadQueue() {
  uploadQueue = [];
  renderUploadQueue();
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function renderUploadQueue() {
  const queueContainer = document.getElementById('upload-queue-container');
  const queueList = document.getElementById('upload-queue-list');
  const startBtn = document.getElementById('start-upload-btn');
  const statusSummary = document.getElementById('upload-status-summary');

  if (uploadQueue.length === 0) {
    queueContainer.classList.add('hidden');
    startBtn.disabled = true;
    statusSummary.innerText = 'Ready';
    return;
  }

  queueContainer.classList.remove('hidden');
  startBtn.disabled = false;
  statusSummary.innerText = `${uploadQueue.length} file(s) queued`;

  let html = '';
  uploadQueue.forEach((item, index) => {
    let statusBadge = '<span class="text-xs text-slate-400">Ready</span>';
    if (item.status === 'uploading') {
      statusBadge = `<span class="text-xs text-blue-600 font-semibold">${item.progress}%</span>`;
    } else if (item.status === 'completed') {
      statusBadge = '<span class="text-xs text-emerald-600 font-semibold">Done ✓</span>';
    } else if (item.status === 'error') {
      statusBadge = `<span class="text-xs text-rose-600 font-semibold" title="${item.error}">Failed ✗</span>`;
    }

    html += `
      <div class="py-2 flex flex-col space-y-1">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-slate-700 truncate max-w-xs">${escapeHtml(item.file.name)}</span>
          <div class="flex items-center space-x-2">
            <span class="text-slate-400 font-mono">${formatBytes(item.file.size)}</span>
            ${statusBadge}
          </div>
        </div>
        <div class="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
          <div class="bg-blue-600 h-1.5 rounded-full transition-all duration-200" style="width: ${item.progress}%"></div>
        </div>
      </div>
    `;
  });

  queueList.innerHTML = html;
}

// Start processing upload queue
async function startUploadQueue() {
  const startBtn = document.getElementById('start-upload-btn');
  startBtn.disabled = true;

  for (let i = 0; i < uploadQueue.length; i++) {
    const item = uploadQueue[i];
    if (item.status === 'completed') continue;

    item.status = 'uploading';
    renderUploadQueue();

    try {
      await uploadSingleFile(item);
      item.status = 'completed';
      item.progress = 100;
    } catch (err) {
      item.status = 'error';
      item.error = err.message;
      showToast(`Upload failed for ${item.file.name}: ${err.message}`, 'error');
    }
    renderUploadQueue();
  }

  showToast('Uploads completed!', 'success');
  refreshCurrentFolder();
}

// Upload a single file using signed URL PUT with XMLHttpRequest progress
function uploadSingleFile(queueItem) {
  return new Promise(async (resolve, reject) => {
    try {
      // 1. Request Signed Upload URL
      const contentType = queueItem.file.type || 'application/octet-stream';
      const urlRes = await fetch('/api/upload-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: queueItem.targetPath,
          content_type: contentType
        })
      });

      if (!urlRes.ok) {
        // Fallback to direct multipart upload if signed URL creation fails
        return uploadFileDirectMultipart(queueItem).then(resolve).catch(reject);
      }

      const { upload_url } = await urlRes.json();

      // 2. Direct PUT to GCS Signed URL
      const xhr = new XMLHttpRequest();
      xhr.open('PUT', upload_url, true);
      xhr.setRequestHeader('Content-Type', contentType);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          queueItem.progress = Math.round((e.loaded / e.total) * 100);
          renderUploadQueue();
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          // If direct upload failed (e.g. CORS), fallback to backend upload
          uploadFileDirectMultipart(queueItem).then(resolve).catch(reject);
        }
      };

      xhr.onerror = () => {
        // Fallback to backend upload
        uploadFileDirectMultipart(queueItem).then(resolve).catch(reject);
      };

      xhr.send(queueItem.file);

    } catch (e) {
      uploadFileDirectMultipart(queueItem).then(resolve).catch(reject);
    }
  });
}

// Fallback direct upload via FastAPI
function uploadFileDirectMultipart(queueItem) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('prefix', currentPath);
    formData.append('file', queueItem.file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload-direct', true);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        queueItem.progress = Math.round((e.loaded / e.total) * 100);
        renderUploadQueue();
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`Server returned ${xhr.status}`));
      }
    };

    xhr.onerror = () => reject(new Error('Network error during upload'));
    xhr.send(formData);
  });
}

// ================= NEW FOLDER MODAL =================

function openFolderModal() {
  document.getElementById('new-folder-name').value = '';
  document.getElementById('folder-modal').classList.remove('hidden');
}

function closeFolderModal() {
  document.getElementById('folder-modal').classList.add('hidden');
}

async function submitNewFolder() {
  const input = document.getElementById('new-folder-name');
  const name = input.value.trim();
  if (!name) {
    showToast('Please provide a folder name', 'warning');
    return;
  }

  const fullPath = currentPath + name + '/';
  try {
    const res = await fetch('/api/create-folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: fullPath })
    });
    if (!res.ok) throw new Error('Failed to create folder');
    closeFolderModal();
    showToast(`Folder "${name}" created`, 'success');
    refreshCurrentFolder();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ================= PREVIEW MODAL =================

async function previewFile(path) {
  try {
    showToast('Loading preview...', 'info');
    const res = await fetch(`/api/preview?path=${encodeURIComponent(path)}`);
    if (!res.ok) throw new Error('Cannot load preview');
    const data = await res.json();

    document.getElementById('preview-file-name').innerText = data.name;
    document.getElementById('preview-file-size').innerText = data.size_formatted;
    document.getElementById('preview-content').innerText = data.content;

    const downloadBtn = document.getElementById('preview-download-btn');
    downloadBtn.onclick = () => downloadFile(data.full_path);

    document.getElementById('preview-modal').classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function closePreviewModal() {
  document.getElementById('preview-modal').classList.add('hidden');
}

// ================= DELETE CONFIRMATION =================

function promptDelete(path) {
  deleteTargetPath = path;
  document.getElementById('delete-item-target').innerText = path;
  document.getElementById('delete-modal').classList.remove('hidden');
}

function closeDeleteModal() {
  deleteTargetPath = null;
  document.getElementById('delete-modal').classList.add('hidden');
}

async function executeDelete() {
  if (!deleteTargetPath) return;

  const btn = document.getElementById('confirm-delete-btn');
  btn.disabled = true;
  btn.innerText = 'Deleting...';

  try {
    const res = await fetch('/api/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: deleteTargetPath })
    });
    if (!res.ok) throw new Error('Deletion failed');

    showToast(`Deleted ${deleteTargetPath}`, 'success');
    closeDeleteModal();
    refreshCurrentFolder();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerText = 'Delete Item';
  }
}
