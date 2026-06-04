import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["generatedImage", "generateLink", "copyButton", "status"];
  static values = { userKey: String };

  connect() {
    this.prefillGenerateLink();
    this.attachInputListeners();
  }

  disconnect() {
    this.revokePreviewObjectUrl();
  }

  prefillGenerateLink() {
    const baseUrl = window.location.origin;
    let prefillText = `${baseUrl}/g?
  style=&
  site=&
  font=&
  title=&
  subtitle=&
  eyebrow=&
  image_url=`;

    if (this.userKeyValue) {
      prefillText += `&
  key=${this.userKeyValue}`;
    }

    this.generateLinkTarget.value = prefillText;
  }

  attachInputListeners() {
    const form = this.element.querySelector('form');
    form.querySelectorAll('input, select').forEach(input => {
      input.addEventListener('input', () => this.updateGenerateLink());
    });
  }

  generate(event) {
    event.preventDefault();
    this.updateGenerateLink();
    this.generateImage();
  }

  updateGenerateLink() {
    const formData = new FormData(this.element.querySelector('form'));
    const params = new URLSearchParams();

    for (const [key, value] of formData.entries()) {
      // Skip the csrfmiddlewaretoken
      if (key !== 'csrfmiddlewaretoken') {
        params.append(key, value || '');
      }
    }

    if (this.userKeyValue) {
      params.append('key', this.userKeyValue);
    }

    const baseUrl = window.location.origin;
    const imageUrl = `/g?${params.toString()}`;
    const fullUrl = `${baseUrl}${imageUrl}`;
    const formattedUrl = fullUrl.replace(/&/g, '&\n  ').replace('?', '?\n  ');
    this.generateLinkTarget.value = formattedUrl;
  }

  generateImage() {
    const imageUrl = this.generateLinkTarget.value.replace(/\s+/g, '');
    this.revokePreviewObjectUrl();
    this.setStatus("Generating");
    this.generatedImageTarget.innerHTML = `
      <div class="px-6 text-center">
        <p class="font-semibold text-[var(--osig-ink)]">Generating preview...</p>
        <p class="mt-2 text-sm text-[var(--osig-muted)]">Fetching the image URL from the server.</p>
      </div>
    `;

    fetch(imageUrl)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Image request failed with status ${response.status}`);
        }

        return response.blob();
      })
      .then(blob => {
        this.revokePreviewObjectUrl();
        this.previewObjectUrl = URL.createObjectURL(blob);
        this.generatedImageTarget.innerHTML = `<img src="${this.previewObjectUrl}" alt="Generated social preview image">`;
        this.setStatus("Generated");
      })
      .catch(error => {
        console.error('Error generating image:', error);
        this.setStatus("Error");
        this.generatedImageTarget.innerHTML = `
          <div class="px-6 text-center">
            <p class="font-semibold text-[var(--osig-danger)]">The preview could not be generated.</p>
            <p class="mt-2 text-sm text-[var(--osig-muted)]">Check the image URL and required text fields, then try again.</p>
          </div>
        `;
      });
  }

  async copyGenerateLink() {
    try {
      await navigator.clipboard.writeText(this.generateLinkTarget.value);
      this.copyButtonTarget.textContent = "Copied!";
      setTimeout(() => {
        this.copyButtonTarget.textContent = "Copy URL";
      }, 2000);
    } catch (err) {
      console.error('Failed to copy: ', err);
    }
  }

  setStatus(status) {
    if (this.hasStatusTarget) {
      this.statusTarget.textContent = status;
    }
  }

  revokePreviewObjectUrl() {
    if (this.previewObjectUrl) {
      URL.revokeObjectURL(this.previewObjectUrl);
      this.previewObjectUrl = null;
    }
  }
}
