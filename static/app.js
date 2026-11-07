// ==============================================================================
// AMBER MULTI-SESSION CHAT CLIENT (Desktop & Mobile Optimized)
// ==============================================================================

const messagesContainer = document.getElementById('messagesContainer');
const welcomeView = document.getElementById('welcomeView');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const voiceBtn = document.getElementById('voiceBtn');
const chatViewport = document.getElementById('chatViewport');
const newChatBtn = document.getElementById('newChatBtn');
const historyList = document.getElementById('historyList');
const settingsModal = document.getElementById('settingsModal');
const openSettingsBtn = document.getElementById('openSettingsBtn');
const openSettingsRailBtn = document.getElementById('openSettingsRailBtn');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const saveKeyBtn = document.getElementById('saveKeyBtn');
const apiKeyField = document.getElementById('apiKeyField');
const menuToggle = document.getElementById('menuToggle');
const closeSidebarBtn = document.getElementById('closeSidebarBtn');
const sidebar = document.getElementById('sidebar');
const railNewChat = document.getElementById('railNewChat');
const railToggleSidebar = document.getElementById('railToggleSidebar');
const railToggleShelf = document.getElementById('railToggleShelf');

// FILE & IMAGE ATTACHMENT ELEMENTS & STATE
const attachBtn = document.getElementById('attachBtn');
const imageFileInput = document.getElementById('imageFileInput');
const imagePreviewContainer = document.getElementById('imagePreviewContainer');
const imagePreviewThumb = document.getElementById('imagePreviewThumb');
const filePreviewBadge = document.getElementById('filePreviewBadge');
const fileBadgeIcon = document.getElementById('fileBadgeIcon');
const fileBadgeExt = document.getElementById('fileBadgeExt');
const imagePreviewName = document.getElementById('imagePreviewName');
const imagePreviewSize = document.getElementById('imagePreviewSize');
const removeImageBtn = document.getElementById('removeImageBtn');

let currentAttachment = null;
let currentImageBase64 = null;
let currentImageMimeType = 'image/jpeg';
let currentImageName = null;

let isGenerating = false;

// SESSIONS STORAGE
let sessions = [];
let currentSessionId = null;

function loadSessionsFromStorage() {
    try {
        const stored = localStorage.getItem('AMBER_SESSIONS') || localStorage.getItem('MENTOR_SESSIONS');
        sessions = stored ? JSON.parse(stored) : [];
    } catch (e) {
        sessions = [];
    }

    if (sessions.length === 0) {
        createNewSession();
    } else {
        const lastActiveId = localStorage.getItem('AMBER_CURRENT_ID') || localStorage.getItem('MENTOR_CURRENT_ID');
        const exists = sessions.find(s => s.id === lastActiveId);
        currentSessionId = exists ? exists.id : sessions[0].id;
        renderSidebarHistory();
        renderCurrentSessionMessages();
    }

    // Sync with server SQLite DB so no conversations or user data are ever lost
    syncSessionsWithServer();
}

async function syncSessionsWithServer() {
    try {
        const res = await fetch('/api/user/sessions');
        if (!res.ok) return;
        const serverSessions = await res.json();
        if (Array.isArray(serverSessions) && serverSessions.length > 0) {
            const map = new Map();
            // Local sessions first
            sessions.forEach(s => map.set(s.id, s));
            // Merge server sessions
            serverSessions.forEach(srv => {
                const sId = srv.session_id;
                if (!map.has(sId)) {
                    map.set(sId, {
                        id: sId,
                        title: srv.title || 'Conversation',
                        createdAt: srv.created_at || new Date().toISOString(),
                        messages: srv.messages || []
                    });
                } else {
                    const local = map.get(sId);
                    if ((!local.messages || local.messages.length === 0) && srv.messages && srv.messages.length > 0) {
                        local.messages = srv.messages;
                    }
                }
            });
            sessions = Array.from(map.values());
            saveSessionsToStorage();
            renderSidebarHistory();
            renderCurrentSessionMessages();
        }
    } catch (e) {
        console.warn('Could not sync sessions with server', e);
    }
}

function saveSessionsToStorage() {
    try {
        localStorage.setItem('AMBER_SESSIONS', JSON.stringify(sessions));
        localStorage.setItem('AMBER_CURRENT_ID', currentSessionId);
    } catch (e) {
        console.warn('Storage quota limit reached, saving pruned sessions...');
        try {
            // Strip heavy image base64 strings from older sessions to prevent quota error
            const pruned = sessions.map((sess, sIdx) => {
                if (sIdx > 0) {
                    return {
                        ...sess,
                        messages: sess.messages.map(m => ({ ...m, image: m.image ? '[attached image]' : undefined }))
                    };
                }
                return sess;
            });
            localStorage.setItem('AMBER_SESSIONS', JSON.stringify(pruned));
        } catch (err) {
            console.error('Could not save sessions', err);
        }
    }
}

function getCurrentSession() {
    return sessions.find(s => s.id === currentSessionId);
}

// CREATE NEW CHAT TAB / SESSION
function createNewSession() {
    const newSession = {
        id: 'session_' + Date.now(),
        title: 'New conversation',
        createdAt: new Date().toISOString(),
        messages: []
    };
    sessions.unshift(newSession);
    currentSessionId = newSession.id;
    saveSessionsToStorage();
    renderSidebarHistory();
    renderCurrentSessionMessages();
    chatInput.value = '';
    chatInput.style.height = 'auto';
    chatInput.focus();

    // Close mobile drawer if open
    if (window.innerWidth <= 900) {
        sidebar.classList.remove('open');
    }
}

// SWITCH TO EXISTING CHAT TAB
function switchSession(sessionId) {
    if (currentSessionId === sessionId) return;
    currentSessionId = sessionId;
    saveSessionsToStorage();
    renderSidebarHistory();
    renderCurrentSessionMessages();

    // Close mobile drawer if open
    if (window.innerWidth <= 900) {
        sidebar.classList.remove('open');
    }
}

// DELETE A CHAT TAB
function deleteSession(sessionId, event) {
    event.stopPropagation();
    sessions = sessions.filter(s => s.id !== sessionId);
    if (sessions.length === 0) {
        createNewSession();
    } else if (currentSessionId === sessionId) {
        currentSessionId = sessions[0].id;
        saveSessionsToStorage();
        renderSidebarHistory();
        renderCurrentSessionMessages();
    } else {
        saveSessionsToStorage();
        renderSidebarHistory();
    }
}

// RENDER SIDEBAR SESSIONS LIST
function renderSidebarHistory() {
    historyList.innerHTML = '';
    sessions.forEach(session => {
        const item = document.createElement('div');
        item.className = `history-item ${session.id === currentSessionId ? 'active' : ''}`;
        item.onclick = () => switchSession(session.id);

        item.innerHTML = `
            <div class="history-content">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                <span class="history-title">${escapeHtml(session.title)}</span>
            </div>
            <button class="delete-chat-btn" title="Delete chat" onclick="deleteSession('${session.id}', event)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
        `;
        historyList.appendChild(item);
    });
}

// RENDER MESSAGES OF CURRENT SESSION
function renderCurrentSessionMessages() {
    messagesContainer.innerHTML = '';
    const session = getCurrentSession();

    if (!session || session.messages.length === 0) {
        welcomeView.style.display = 'block';
    } else {
        welcomeView.style.display = 'none';
        session.messages.forEach(msg => {
            appendMessageRow(msg.role, msg.content, false, msg.attachment || msg.image || null);
        });
        chatViewport.scrollTop = chatViewport.scrollHeight;
    }
}

// FILE SIZE FORMATTER HELPER
function formatFileSize(bytes) {
    if (!bytes || bytes < 1024) return `${bytes || 0} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// FILE & IMAGE ATTACHMENT HANDLERS
function handleFileSelect(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    processSelectedFile(file);
}

function processSelectedFile(file) {
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) {
        alert('File ka size 25MB se kam hona chahiye.');
        return;
    }

    const name = file.name || 'document';
    const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
    const mime = file.type || '';

    const isImage = mime.startsWith('image/') || ['png', 'jpg', 'jpeg', 'webp', 'gif', 'svg', 'bmp'].includes(ext);
    const isPdf = mime === 'application/pdf' || ext === 'pdf';

    if (isImage) {
        const reader = new FileReader();
        reader.onload = function(evt) {
            currentAttachment = {
                type: 'image',
                name: name,
                mime: mime || 'image/jpeg',
                size: file.size,
                data: evt.target.result
            };
            currentImageBase64 = evt.target.result;
            currentImageMimeType = currentAttachment.mime;
            currentImageName = name;

            if (imagePreviewThumb) {
                imagePreviewThumb.src = evt.target.result;
                imagePreviewThumb.style.display = 'block';
            }
            if (filePreviewBadge) filePreviewBadge.style.display = 'none';
            if (imagePreviewName) imagePreviewName.textContent = name;
            if (imagePreviewSize) imagePreviewSize.textContent = formatFileSize(file.size);
            if (imagePreviewContainer) imagePreviewContainer.style.display = 'flex';
            chatInput.focus();
        };
        reader.readAsDataURL(file);
    } else if (isPdf) {
        const reader = new FileReader();
        reader.onload = function(evt) {
            currentAttachment = {
                type: 'pdf',
                name: name,
                mime: 'application/pdf',
                size: file.size,
                data: evt.target.result
            };
            currentImageBase64 = evt.target.result;
            currentImageMimeType = 'application/pdf';
            currentImageName = name;

            if (imagePreviewThumb) imagePreviewThumb.style.display = 'none';
            if (filePreviewBadge) {
                if (fileBadgeIcon) fileBadgeIcon.textContent = '📑';
                if (fileBadgeExt) fileBadgeExt.textContent = 'PDF';
                filePreviewBadge.style.display = 'flex';
            }
            if (imagePreviewName) imagePreviewName.textContent = name;
            if (imagePreviewSize) imagePreviewSize.textContent = formatFileSize(file.size);
            if (imagePreviewContainer) imagePreviewContainer.style.display = 'flex';
            chatInput.focus();
        };
        reader.readAsDataURL(file);
    } else {
        // HTML, TXT, MD, JSON, JS, PY, CSS, CSV, etc.
        const reader = new FileReader();
        reader.onload = function(evt) {
            currentAttachment = {
                type: 'text',
                name: name,
                mime: mime || 'text/html',
                size: file.size,
                content: evt.target.result
            };
            currentImageBase64 = null;
            currentImageName = name;

            if (imagePreviewThumb) imagePreviewThumb.style.display = 'none';
            if (filePreviewBadge) {
                const icon = (ext === 'html' || ext === 'htm') ? '🌐' : '📄';
                if (fileBadgeIcon) fileBadgeIcon.textContent = icon;
                if (fileBadgeExt) fileBadgeExt.textContent = ext.toUpperCase().slice(0, 4) || 'DOC';
                filePreviewBadge.style.display = 'flex';
            }
            if (imagePreviewName) imagePreviewName.textContent = name;
            if (imagePreviewSize) imagePreviewSize.textContent = formatFileSize(file.size);
            if (imagePreviewContainer) imagePreviewContainer.style.display = 'flex';
            chatInput.focus();
        };
        reader.readAsText(file);
    }
}

function clearAttachment() {
    currentAttachment = null;
    currentImageBase64 = null;
    currentImageMimeType = 'image/jpeg';
    currentImageName = null;
    if (imageFileInput) imageFileInput.value = '';
    if (imagePreviewContainer) imagePreviewContainer.style.display = 'none';
    if (imagePreviewThumb) {
        imagePreviewThumb.src = '';
        imagePreviewThumb.style.display = 'none';
    }
    if (filePreviewBadge) filePreviewBadge.style.display = 'none';
}

attachBtn?.addEventListener('click', () => imageFileInput?.click());
imageFileInput?.addEventListener('change', handleFileSelect);
removeImageBtn?.addEventListener('click', clearAttachment);

// Support Ctrl+V paste of images or files
window.addEventListener('paste', (e) => {
    const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items;
    if (!items) return;
    for (const item of items) {
        const file = item.getAsFile();
        if (file) {
            processSelectedFile(file);
            break;
        }
    }
});

// AUTO EXPAND TEXTAREA
chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + 'px';
});

// ENTER TO SEND
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

sendBtn.addEventListener('click', sendMessage);
newChatBtn.addEventListener('click', createNewSession);
railNewChat?.addEventListener('click', createNewSession);

// MOBILE MENU TOGGLES
menuToggle?.addEventListener('click', () => {
    sidebar.classList.toggle('open');
});
closeSidebarBtn?.addEventListener('click', () => {
    sidebar.classList.remove('open');
});

// SETTINGS MODAL
const openModal = () => settingsModal.classList.add('open');
const closeModal = () => settingsModal.classList.remove('open');

openSettingsBtn?.addEventListener('click', openModal);
openSettingsRailBtn?.addEventListener('click', openModal);
closeSettingsBtn?.addEventListener('click', closeModal);

// GENDER PREFERENCE SETUP
const genderSelect = document.getElementById('genderSelect');
if (genderSelect) {
    const savedGender = localStorage.getItem('AMBER_GENDER') || 'auto';
    genderSelect.value = savedGender;
    genderSelect.addEventListener('change', (e) => {
        localStorage.setItem('AMBER_GENDER', e.target.value);
    });
}

saveKeyBtn?.addEventListener('click', async () => {
    const key = apiKeyField.value.trim();
    if (!key) return;
    try {
        await fetch('/api/save_key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: key })
        });
        closeModal();
        alert('API Key successfully saved in .env!');
    } catch (e) {
        closeModal();
    }
});

// SEND MESSAGE FUNCTION
async function sendMessage() {
    const text = chatInput.value.trim();
    const hasAttachment = !!currentAttachment;
    if ((!text && !hasAttachment) || isGenerating) return;

    let session = getCurrentSession();
    if (!session) {
        createNewSession();
        session = getCurrentSession();
    }

    const attachmentPayload = currentAttachment ? { ...currentAttachment } : null;

    // Auto update title if this is the first message
    if (session.messages.length === 0) {
        let titleText = text;
        if (!titleText && attachmentPayload) {
            titleText = (attachmentPayload.type === 'image') ? "🖼️ Image Query" : `📄 ${attachmentPayload.name}`;
        }
        titleText = titleText || "Conversation";
        session.title = titleText.slice(0, 26) + (titleText.length > 26 ? '...' : '');
        renderSidebarHistory();
    }

    welcomeView.style.display = 'none';

    // Add User Message (include attached image or file if present)
    const userMsgObj = { 
        role: 'user', 
        content: text,
        attachment: attachmentPayload
    };
    if (attachmentPayload && (attachmentPayload.type === 'image' || attachmentPayload.type === 'pdf')) {
        userMsgObj.image = attachmentPayload.data;
    }
    session.messages.push(userMsgObj);
    saveSessionsToStorage();
    appendMessageRow('user', text, true, attachmentPayload);

    chatInput.value = '';
    chatInput.style.height = 'auto';
    clearAttachment();
    isGenerating = true;

    // Thinking indicator
    const thinkingRow = appendThinkingRow();
    chatViewport.scrollTop = chatViewport.scrollHeight;

    try {
        // Send history of current session to API
        const historyForApi = session.messages.slice(0, -1).map(m => ({
            role: m.role === 'user' ? 'user' : 'model',
            content: m.content
        }));

        const currentGender = localStorage.getItem('AMBER_GENDER') || 'auto';
        const currentUserName = localStorage.getItem('AMBER_USER_NAME') || 'User';
        const currentUserAvatar = localStorage.getItem('AMBER_USER_AVATAR') || null;

        const reqBody = {
            message: text,
            session_id: session.id,
            history: historyForApi,
            gender: currentGender,
            user_name: currentUserName,
            user_avatar: currentUserAvatar
        };

        if (attachmentPayload) {
            reqBody.file_name = attachmentPayload.name;
            reqBody.file_type = attachmentPayload.type;
            if (attachmentPayload.type === 'image' || attachmentPayload.type === 'pdf') {
                reqBody.image_base64 = attachmentPayload.data;
                reqBody.image_mime_type = attachmentPayload.mime;
            } else if (attachmentPayload.type === 'text') {
                reqBody.file_content = attachmentPayload.content;
            }
        }

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reqBody)
        });

        const data = await response.json();
        thinkingRow.remove();

        if (data.reply) {
            session.messages.push({ role: 'model', content: data.reply });
            saveSessionsToStorage();
            appendMessageRow('model', data.reply, true);
        } else {
            appendMessageRow('model', "Maaf kijiyega, rabta nahi ho saka. Dobara koshish karein.", true);
        }
    } catch (err) {
        thinkingRow.remove();
        appendMessageRow('model', "Server connection error. Please verify backend.", true);
        console.error(err);
    } finally {
        isGenerating = false;
        chatViewport.scrollTop = chatViewport.scrollHeight;
    }
}

// APPEND MESSAGE ROW
function appendMessageRow(role, text, scroll = true, attachment = null) {
    const isUser = role === 'user';
    const row = document.createElement('div');
    row.className = `msg-row ${isUser ? 'user' : 'bot'}`;

    const avatar = document.createElement('div');
    avatar.className = `msg-avatar ${isUser ? 'user' : 'bot'}`;
    if (isUser) {
        const userAvatarImg = localStorage.getItem('AMBER_USER_AVATAR');
        const userName = localStorage.getItem('AMBER_USER_NAME') || '';
        if (userAvatarImg) {
            avatar.innerHTML = `<img src="${userAvatarImg}" alt="${escapeHtml(userName || 'User')}">`;
        } else {
            avatar.textContent = userName ? userName[0].toUpperCase() : 'You';
        }
        avatar.title = userName || 'You';
    } else {
        avatar.innerHTML = '<img src="/static/logo.png" onerror="this.onerror=null; this.src=\'/static/logo.svg\';" class="avatar-crest" alt="Amber">';
    }

    const body = document.createElement('div');
    body.className = 'msg-body';

    // If attached image or document exists, render preview card
    if (attachment) {
        if (typeof attachment === 'string' && attachment.startsWith('data:image')) {
            const img = document.createElement('img');
            img.src = attachment;
            img.alt = 'Uploaded image';
            img.className = 'chat-attached-image';
            img.onclick = () => window.open(attachment, '_blank');
            body.appendChild(img);
        } else if (typeof attachment === 'object') {
            if (attachment.type === 'image' && attachment.data) {
                const img = document.createElement('img');
                img.src = attachment.data;
                img.alt = 'Uploaded image';
                img.className = 'chat-attached-image';
                img.onclick = () => window.open(attachment.data, '_blank');
                body.appendChild(img);
            } else if (attachment.name) {
                const docCard = document.createElement('div');
                docCard.className = 'chat-attached-doc';
                const lowerName = attachment.name.toLowerCase();
                const icon = (lowerName.endsWith('.html') || lowerName.endsWith('.htm')) ? '🌐' : (lowerName.endsWith('.pdf') ? '📑' : '📄');
                const sizeStr = attachment.size ? `${formatFileSize(attachment.size)} • ` : '';
                docCard.innerHTML = `
                    <div class="doc-icon">${icon}</div>
                    <div class="doc-details">
                        <span class="doc-title">${escapeHtml(attachment.name)}</span>
                        <span class="doc-sub">${sizeStr}Attached Document</span>
                    </div>
                `;
                body.appendChild(docCard);
            }
        }
    }

    if (text) {
        const textWrapper = document.createElement('div');
        textWrapper.innerHTML = formatMarkdown(text);
        body.appendChild(textWrapper);
    }

    if (isUser) {
        row.appendChild(body);
        row.appendChild(avatar);
    } else {
        row.appendChild(avatar);
        row.appendChild(body);
    }

    messagesContainer.appendChild(row);
    if (scroll) {
        chatViewport.scrollTop = chatViewport.scrollHeight;
    }
    return row;
}

// THINKING ROW
function appendThinkingRow() {
    const row = document.createElement('div');
    row.className = 'msg-row bot';

    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar bot';
    avatar.innerHTML = '<img src="/static/logo.png" onerror="this.onerror=null; this.src=\'/static/logo.svg\';" class="avatar-crest" alt="Amber">';

    const body = document.createElement('div');
    body.className = 'msg-body';
    body.innerHTML = '<span style="color: var(--amber-light); font-size: 13.5px; opacity: 0.85;">Amber is thinking & reflecting...</span>';

    row.appendChild(avatar);
    row.appendChild(body);
    messagesContainer.appendChild(row);
    return row;
}

// FORMAT MARKDOWN
function formatMarkdown(text) {
    let formatted = escapeHtml(text);

    // Bold
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italics
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Quotes
    formatted = formatted.replace(/^(&gt;|>)\s*(.*$)/gim, '<blockquote>$2</blockquote>');

    // Paragraphs
    const paragraphs = formatted.split(/\n\n+/);
    return paragraphs.map(p => {
        if (p.startsWith('<blockquote>')) return p;
        return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join('');
}

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// VOICE INPUT
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'ur-PK';

    recognition.onstart = () => voiceBtn.classList.add('recording');
    recognition.onend = () => voiceBtn.classList.remove('recording');
    recognition.onerror = () => voiceBtn.classList.remove('recording');

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        chatInput.value += (chatInput.value ? ' ' : '') + transcript;
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + 'px';
    };

    voiceBtn.addEventListener('click', () => {
        if (voiceBtn.classList.contains('recording')) {
            recognition.stop();
        } else {
            recognition.start();
        }
    });
} else {
    voiceBtn.style.display = 'none';
}

// OWNER AUTH CLIENT LOGIC
async function checkOwnerAuthOnClient() {
    try {
        const res = await fetch('/api/admin/check_auth');
        const data = await res.json();
        const sidebarOwner = document.getElementById('sidebarOwnerSection');
        const headerOwner = document.getElementById('headerOwnerSection');
        const ownerStatusText = document.getElementById('ownerStatusText');
        const ownerLoginForm = document.getElementById('ownerLoginForm');
        const ownerSuccessMsg = document.getElementById('ownerSuccessMsg');
        const lockOwnerBtn = document.getElementById('lockOwnerBtn');

        if (data.is_owner) {
            if (sidebarOwner) sidebarOwner.style.display = 'block';
            if (headerOwner) headerOwner.style.display = 'block';
            if (ownerStatusText) ownerStatusText.textContent = 'Aap Owner ke tor par authenticated hain. Admin buttons active hain.';
            if (ownerLoginForm) ownerLoginForm.style.display = 'none';
            if (ownerSuccessMsg) ownerSuccessMsg.style.display = 'block';
            if (lockOwnerBtn) lockOwnerBtn.style.display = 'inline-block';
        } else {
            if (sidebarOwner) sidebarOwner.style.display = 'none';
            if (headerOwner) headerOwner.style.display = 'none';
            if (ownerStatusText) ownerStatusText.textContent = 'Agar aap owner hain toh apna Master Password darj karein taake Admin Panel unlock ho jaye.';
            if (ownerLoginForm) ownerLoginForm.style.display = 'flex';
            if (ownerSuccessMsg) ownerSuccessMsg.style.display = 'none';
            if (lockOwnerBtn) lockOwnerBtn.style.display = 'none';
        }
    } catch (e) {
        // Not authenticated
    }
}

document.getElementById('unlockOwnerBtn')?.addEventListener('click', async () => {
    const pwInput = document.getElementById('ownerModalPassword');
    const pw = pwInput?.value.trim();
    if (!pw) return;

    try {
        const res = await fetch('/api/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: pw })
        });

        if (res.ok) {
            pwInput.value = '';
            alert('✅ Owner verified successfully! Admin buttons are now unlocked.');
            checkOwnerAuthOnClient();
        } else {
            alert('❌ Ghalat password! Durust password darj karein.');
        }
    } catch (err) {
        alert('Server rabta nahi ho saka.');
    }
});

document.getElementById('lockOwnerBtn')?.addEventListener('click', async () => {
    try {
        await fetch('/api/admin/logout', { method: 'POST' });
        alert('Owner panel locked. Admin buttons hide ho gaye hain.');
        checkOwnerAuthOnClient();
    } catch (e) {}
});

// ================= USER PROFILE MANAGEMENT =================
const openProfileBtn = document.getElementById('openProfileBtn');
const profileModal = document.getElementById('profileModal');
const closeProfileBtn = document.getElementById('closeProfileBtn');
const saveProfileBtn = document.getElementById('saveProfileBtn');
const userNameInput = document.getElementById('userNameInput');
const profileGenderSelect = document.getElementById('profileGenderSelect');
const uploadAvatarBtn = document.getElementById('uploadAvatarBtn');
const removeAvatarBtn = document.getElementById('removeAvatarBtn');
const profileAvatarInput = document.getElementById('profileAvatarInput');
const modalAvatarPreview = document.getElementById('modalAvatarPreview');
const userPillAvatar = document.getElementById('userPillAvatar');
const userPillName = document.getElementById('userPillName');

let tempAvatarBase64 = null;

function loadUserProfile() {
    const name = localStorage.getItem('AMBER_USER_NAME') || '';
    const avatar = localStorage.getItem('AMBER_USER_AVATAR') || '';
    const gender = localStorage.getItem('AMBER_GENDER') || 'auto';

    if (userNameInput) userNameInput.value = name;
    if (profileGenderSelect) profileGenderSelect.value = gender;
    tempAvatarBase64 = avatar || null;

    renderProfileUI(name, avatar);
}

function renderProfileUI(name, avatar) {
    const displayName = name || 'Guest User';
    const initial = (name ? name[0] : 'U').toUpperCase();

    if (userPillName) userPillName.textContent = displayName;

    if (avatar) {
        if (userPillAvatar) userPillAvatar.innerHTML = `<img src="${avatar}" alt="${escapeHtml(displayName)}">`;
        if (modalAvatarPreview) modalAvatarPreview.innerHTML = `<img src="${avatar}" style="width:100%;height:100%;object-fit:cover;" alt="Avatar">`;
    } else {
        if (userPillAvatar) userPillAvatar.innerHTML = `<span id="userPillInitial">${initial}</span>`;
        if (modalAvatarPreview) modalAvatarPreview.innerHTML = `<span id="modalAvatarInitial">${initial}</span>`;
    }
}

openProfileBtn?.addEventListener('click', () => {
    loadUserProfile();
    profileModal?.classList.add('open');
});

closeProfileBtn?.addEventListener('click', () => {
    profileModal?.classList.remove('open');
});

uploadAvatarBtn?.addEventListener('click', () => {
    profileAvatarInput?.click();
});

profileAvatarInput?.addEventListener('change', (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
        alert('Barah-e-karam sirf tasweer upload karein.');
        return;
    }
    const reader = new FileReader();
    reader.onload = (evt) => {
        tempAvatarBase64 = evt.target.result;
        renderProfileUI(userNameInput ? userNameInput.value.trim() : '', tempAvatarBase64);
    };
    reader.readAsDataURL(file);
});

removeAvatarBtn?.addEventListener('click', () => {
    tempAvatarBase64 = null;
    if (profileAvatarInput) profileAvatarInput.value = '';
    renderProfileUI(userNameInput ? userNameInput.value.trim() : '', null);
});

saveProfileBtn?.addEventListener('click', () => {
    const name = userNameInput ? userNameInput.value.trim() : '';
    const gender = profileGenderSelect ? profileGenderSelect.value : 'auto';

    if (name) {
        localStorage.setItem('AMBER_USER_NAME', name);
    } else {
        localStorage.removeItem('AMBER_USER_NAME');
    }

    if (tempAvatarBase64) {
        localStorage.setItem('AMBER_USER_AVATAR', tempAvatarBase64);
    } else {
        localStorage.removeItem('AMBER_USER_AVATAR');
    }

    localStorage.setItem('AMBER_GENDER', gender);
    const genderSel = document.getElementById('genderSelect');
    if (genderSel) genderSel.value = gender;

    renderProfileUI(name, tempAvatarBase64);
    profileModal?.classList.remove('open');
    renderCurrentSessionMessages();
    alert('✅ Profile kamyabi se save ho gaya!');
});

// INITIALIZE ON LOAD
loadSessionsFromStorage();
loadUserProfile();
checkOwnerAuthOnClient();
