/**
 * Image gallery controller
 */
class ImageGalleryController {
    constructor(wsClient) {
        this.wsClient = wsClient;
        this.gallery = document.getElementById('image-gallery');
        this.imageCount = document.getElementById('image-count');
        this.modal = document.getElementById('image-modal');
        this.modalImage = document.getElementById('modal-image');
        this.imageInfo = document.getElementById('image-info');
        this.images = [];

        this.setupWebSocketListeners();
        this.setupModalListeners();
    }

    setupWebSocketListeners() {
        this.wsClient.on('image_ready', (data) => {
            this.loadImages(data.run_id);
        });
    }

    setupModalListeners() {
        const closeBtn = this.modal.querySelector('.close-modal');
        closeBtn.addEventListener('click', () => this.closeModal());

        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.closeModal();
            }
        });
    }

    async loadImages(runId) {
        try {
            const response = await fetch(`/api/outputs/${runId}/images`);
            const data = await response.json();

            for (const image of data.images) {
                this.addImage(runId, image);
            }

            this.updateImageCount();
        } catch (error) {
            console.error('Error loading images:', error);
        }
    }

    addImage(runId, imageData) {
        // Remove placeholder
        const placeholder = this.gallery.querySelector('.placeholder');
        if (placeholder) placeholder.remove();

        // Check if image already exists
        if (this.images.some(img => img.url === imageData.url)) {
            return;
        }

        this.images.push(imageData);

        const imageDiv = document.createElement('div');
        imageDiv.className = 'image-item';

        // Determine label based on filename
        let label = imageData.filename;
        let badge = '';
        if (imageData.filename.includes('water_mask')) {
            label = 'Water Mask';
            badge = '<div class="image-badge">MASK</div>';
        } else if (imageData.filename.includes('overlay')) {
            label = 'Overlay';
            badge = '<div class="image-badge">OVERLAY</div>';
        } else if (imageData.filename.includes('original') || imageData.filename.includes('viz')) {
            label = 'Original';
            badge = '<div class="image-badge">RGB</div>';
        }

        imageDiv.innerHTML = `
            ${badge}
            <img src="${imageData.url}" alt="${label}" loading="lazy">
            <div class="image-label">${label}</div>
        `;

        imageDiv.addEventListener('click', () => {
            this.openModal(imageData.url, label, runId);
        });

        this.gallery.appendChild(imageDiv);
    }

    openModal(imageUrl, label, runId) {
        this.modalImage.src = imageUrl;
        this.imageInfo.innerHTML = `
            <strong>${label}</strong><br>
            Run ID: ${runId}
        `;
        this.modal.classList.add('active');
    }

    closeModal() {
        this.modal.classList.remove('active');
        this.modalImage.src = '';
    }

    updateImageCount() {
        this.imageCount.textContent = `${this.images.length} image${this.images.length !== 1 ? 's' : ''}`;
    }

    displayImages(imagePaths) {
        /**
         * Display images in three auto-cycling rows (RGB, MASK, OVERLAY)
         * @param {string[]} imagePaths - Array of image URLs
         */
        console.log('[ImageGallery] Displaying images:', imagePaths);

        // Filter out TIF files, only keep WEBP
        const webpPaths = imagePaths.filter(path => path.endsWith('.webp'));

        // Group by category
        const grouped = {
            rgb: webpPaths.filter(p => p.includes('original') || p.includes('viz')),
            mask: webpPaths.filter(p => p.includes('water_mask')),
            overlay: webpPaths.filter(p => p.includes('overlay'))
        };

        console.log('[ImageGallery] Grouped:', grouped);

        // Clear gallery and remove placeholder
        this.gallery.innerHTML = '';
        this.images = [];

        // Create first row with RGB and MASK side-by-side
        const firstRow = document.createElement('div');
        firstRow.className = 'image-double-row';
        this.gallery.appendChild(firstRow);

        // Create second row with OVERLAY
        const secondRow = document.createElement('div');
        secondRow.className = 'image-single-row';
        this.gallery.appendChild(secondRow);

        // Add images to respective rows
        this.createCyclingRowInContainer(firstRow, 'RGB Original', grouped.rgb, 'rgb');
        this.createCyclingRowInContainer(firstRow, 'Water Mask', grouped.mask, 'mask');
        this.createCyclingRowInContainer(secondRow, 'Overlay', grouped.overlay, 'overlay');

        this.updateImageCount();
    }

    createCyclingRowInContainer(container, title, imagePaths, category) {
        if (imagePaths.length === 0) return;

        const rowDiv = document.createElement('div');
        rowDiv.className = 'image-row';
        rowDiv.dataset.category = category;

        const headerDiv = document.createElement('div');
        headerDiv.className = 'image-row-header';
        headerDiv.innerHTML = `
            <span class="row-title">${title}</span>
            <span class="row-counter">1 / ${imagePaths.length}</span>
        `;

        const imageContainer = document.createElement('div');
        imageContainer.className = 'image-container';

        const img = document.createElement('img');
        img.src = imagePaths[0];
        img.alt = title;
        img.className = 'cycling-image';
        img.addEventListener('click', () => {
            this.openModal(imagePaths[this.currentIndices[category] || 0], title, 'latest');
        });

        imageContainer.appendChild(img);
        rowDiv.appendChild(headerDiv);
        rowDiv.appendChild(imageContainer);
        container.appendChild(rowDiv);

        // Store image paths for cycling
        if (!this.cyclingImages) this.cyclingImages = {};
        if (!this.currentIndices) this.currentIndices = {};

        this.cyclingImages[category] = imagePaths;
        this.currentIndices[category] = 0;

        // Auto-cycle every 2 seconds if more than 1 image
        if (imagePaths.length > 1) {
            setInterval(() => {
                this.cycleImage(category);
            }, 2000);
        }

        // Store for count
        this.images.push(...imagePaths.map(path => ({ url: path })));
    }

    cycleImage(category) {
        const images = this.cyclingImages[category];
        if (!images || images.length <= 1) return;

        // Increment index
        this.currentIndices[category] = (this.currentIndices[category] + 1) % images.length;
        const index = this.currentIndices[category];

        // Update image source
        const row = this.gallery.querySelector(`[data-category="${category}"]`);
        if (row) {
            const img = row.querySelector('.cycling-image');
            const counter = row.querySelector('.row-counter');

            if (img) img.src = images[index];
            if (counter) counter.textContent = `${index + 1} / ${images.length}`;
        }
    }

    clear() {
        this.gallery.innerHTML = '<p class="placeholder">Images will appear here</p>';
        this.images = [];
        this.updateImageCount();
    }
}

window.ImageGalleryController = ImageGalleryController;
