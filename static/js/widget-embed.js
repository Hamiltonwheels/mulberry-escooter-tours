(function() {
        const BASE_URL = window.MST_BASE_URL || '';
            const container = document.getElementById('mst-booking-widget');
                if (!container) return;
                    const iframe = document.createElement('iframe');
                        iframe.src = BASE_URL + '/widget';
                            iframe.style.cssText = 'width:100%;max-width:420px;height:480px;border:none;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,.1);';
                                iframe.title = 'Book an E-Scooter Tour';
                                    iframe.loading = 'lazy';
                                        container.appendChild(iframe);
                                        })();
                                        
})