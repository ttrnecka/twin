(() => {
  // 1. Dynamically find the running script tag to grab the origin domain
  const currentScript = document.currentScript as HTMLScriptElement;
  let baseUrl = process.env.NEXT_PUBLIC_FRONT_URL || 'http://localhost:8000'; // Fallback if parsing fails

  if (currentScript && currentScript.src) {
    try {
      const url = new URL(currentScript.src);
      baseUrl = url.origin;
    } catch (e) {
      console.error('Failed to parse widget script origin, using default fallback.', e);
    }
  }

  // 2. Create a container element for the Shadow DOM
  const container = document.createElement('div');
  container.id = 'ai-twin-widget-root';
  document.body.appendChild(container);

  const shadow = container.attachShadow({ mode: 'open' });

  // 3. Inject styles and structure with the dynamic template literal baseUrl
  shadow.innerHTML = `
    <style>
      .chat-trigger {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #0070f3;
        color: white;
        border: none;
        border-radius: 50%;
        width: 60px;
        height: 60px;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        font-size: 24px;
        z-index: 999999;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .chat-window {
        display: none;
        position: fixed;
        bottom: 90px;
        right: 20px;
        width: 380px;
        height: 600px;
        background: white;
        box-shadow: 0 5px 40px rgba(0,0,0,0.16);
        border-radius: 12px;
        overflow: hidden;
        z-index: 999999;
        transition: all 0.3s ease;
      }
      .chat-window.open {
        display: block;
      }
      iframe {
        width: 100%;
        height: 100%;
        border: none;
      }
    </style>

    <button class="chat-trigger" id="widget-btn">💬</button>
    <div class="chat-window" id="widget-window">
      <iframe src="${baseUrl}/chat-embed.html"></iframe>
    </div>
  `;

  // 4. Handle window visibility toggle
  const btn = shadow.getElementById('widget-btn') as HTMLButtonElement | null;
  const windowEl = shadow.getElementById('widget-window') as HTMLDivElement | null;

  if (btn && windowEl) {
    btn.addEventListener('click', () => {
      windowEl.classList.toggle('open');
      btn.innerText = windowEl.classList.contains('open') ? '✕' : '💬';
    });
  }
})();