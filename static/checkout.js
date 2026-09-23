(function () {
    class PaymentGatewayCheckout {
        constructor() {
            this.container = null;
            this.iframe = null;
            this.backdrop = null;
            this.options = null;
            
            // Listen for messages from the iframe
            window.addEventListener('message', this.handleMessage.bind(this));
        }

        open(options) {
            if (!options.order_id || !options.key_id) {
                console.error("PaymentGateway: order_id and key_id are required.");
                if (options.onError) options.onError("Missing required parameters.");
                return;
            }

            this.options = options;
            this.injectUI();
            
            // Allow DOM to update before triggering animation
            requestAnimationFrame(() => {
                this.backdrop.style.opacity = '1';
                this.iframe.style.transform = 'translate(-50%, -50%) scale(1)';
                this.iframe.style.opacity = '1';
            });
        }

        close() {
            if (!this.container) return;
            
            // Animate out
            this.backdrop.style.opacity = '0';
            this.iframe.style.transform = 'translate(-50%, -45%) scale(0.95)';
            this.iframe.style.opacity = '0';
            
            // Remove from DOM after animation
            setTimeout(() => {
                if (this.container && this.container.parentNode) {
                    this.container.parentNode.removeChild(this.container);
                }
                this.container = null;
                this.iframe = null;
                this.backdrop = null;
            }, 300);
        }

        handleMessage(event) {
            // In a real app, verify event.origin here
            if (!event.data || !event.data.type) return;

            switch (event.data.type) {
                case 'PAYMENT_SUCCESS':
                    this.close();
                    if (this.options.onSuccess) {
                        this.options.onSuccess(event.data.payload);
                    }
                    break;
                case 'PAYMENT_ERROR':
                    if (this.options.onError) {
                        this.options.onError(event.data.payload);
                    }
                    break;
                case 'CLOSE_MODAL':
                    this.close();
                    break;
            }
        }

        injectUI() {
            // Container
            this.container = document.createElement('div');
            this.container.id = 'pg-checkout-container';
            this.container.style.position = 'fixed';
            this.container.style.top = '0';
            this.container.style.left = '0';
            this.container.style.width = '100vw';
            this.container.style.height = '100vh';
            this.container.style.zIndex = '999999';
            
            // Backdrop with blur
            this.backdrop = document.createElement('div');
            this.backdrop.style.position = 'absolute';
            this.backdrop.style.top = '0';
            this.backdrop.style.left = '0';
            this.backdrop.style.width = '100%';
            this.backdrop.style.height = '100%';
            this.backdrop.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
            this.backdrop.style.backdropFilter = 'blur(5px)';
            this.backdrop.style.opacity = '0';
            this.backdrop.style.transition = 'opacity 0.3s ease';
            this.backdrop.style.cursor = 'pointer';
            
            // Close on backdrop click
            this.backdrop.addEventListener('click', () => this.close());
            
            // Iframe
            this.iframe = document.createElement('iframe');
            // Hardcoded to localhost:8000 for demo, in prod this would be the gateway domain
            const baseUrl = window.location.origin;
            this.iframe.src = `${baseUrl}/static/checkout.html`;
            this.iframe.style.position = 'absolute';
            this.iframe.style.top = '50%';
            this.iframe.style.left = '50%';
            this.iframe.style.transform = 'translate(-50%, -45%) scale(0.95)';
            this.iframe.style.width = '100%';
            this.iframe.style.maxWidth = '420px';
            this.iframe.style.height = '600px';
            this.iframe.style.border = 'none';
            this.iframe.style.borderRadius = '20px';
            this.iframe.style.opacity = '0';
            this.iframe.style.transition = 'all 0.4s cubic-bezier(0.25, 1, 0.5, 1)';
            this.iframe.style.boxShadow = '0 25px 50px -12px rgba(0, 0, 0, 0.5)';
            
            // When iframe loads, send initialization data
            this.iframe.onload = () => {
                this.iframe.contentWindow.postMessage({
                    type: 'INIT_CHECKOUT',
                    payload: {
                        order_id: this.options.order_id,
                        key_id: this.options.key_id,
                        amount: this.options.amount || 0
                    }
                }, '*');
            };

            this.container.appendChild(this.backdrop);
            this.container.appendChild(this.iframe);
            document.body.appendChild(this.container);
        }
    }

    // Expose globally
    window.PaymentGateway = new PaymentGatewayCheckout();
})();
