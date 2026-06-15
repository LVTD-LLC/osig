import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["form", "preview", "status", "warnings", "metadata", "export", "copyButton", "downloadButton"];
  static values = { renderUrl: String };

  render(event) {
    event.preventDefault();
    const spec = this.collectSpec();

    this.setStatus("Rendering");
    this.renderSkeleton();

    fetch(this.renderUrlValue, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": this.csrfToken(),
      },
      body: JSON.stringify({ spec }),
    })
      .then(async response => {
        const payload = await response.json();
        if (!response.ok) {
          throw payload;
        }
        return payload;
      })
      .then(payload => this.renderSuccess(payload))
      .catch(error => this.renderError(error));
  }

  collectSpec() {
    const formData = new FormData(this.formTarget);
    const spec = {};

    for (const [key, rawValue] of formData.entries()) {
      if (key === "csrfmiddlewaretoken") {
        continue;
      }

      const value = typeof rawValue === "string" ? rawValue.trim() : rawValue;
      if (value === "") {
        continue;
      }

      if (["quality", "max_kb"].includes(key)) {
        spec[key] = Number(value);
      } else {
        spec[key] = value;
      }
    }

    return spec;
  }

  renderSkeleton() {
    this.previewTarget.innerHTML = `
      <div class="preview-skeleton" aria-hidden="true">
        <span></span>
        <span></span>
        <span></span>
      </div>
    `;
    this.hideWarnings();
  }

  renderSuccess(payload) {
    this.latestPayload = payload;
    this.setStatus("Rendered");

    this.previewTarget.innerHTML = `<img src="${payload.data_uri}" alt="Generated social preview image">`;
    this.renderWarnings(payload.warnings || []);
    this.renderMetadata(payload);
    this.exportTarget.value = JSON.stringify(this.exportPayload(payload), null, 2);
    this.downloadButtonTarget.disabled = false;
  }

  renderError(error) {
    console.error("Studio render failed:", error);
    this.latestPayload = null;
    this.setStatus("Error");
    this.downloadButtonTarget.disabled = true;

    const message = error?.message || "The image could not be rendered.";
    this.previewTarget.innerHTML = `
      <div class="px-6 text-center">
        <p class="font-semibold text-[var(--osig-danger)]">${this.escapeHtml(message)}</p>
        <p class="mt-2 text-sm text-[var(--osig-muted)]">Adjust the spec or image URL, then render again.</p>
      </div>
    `;
    this.renderWarnings(error?.details ? [JSON.stringify(error.details)] : []);
  }

  renderWarnings(warnings) {
    if (!warnings.length) {
      this.hideWarnings();
      return;
    }

    this.warningsTarget.classList.remove("hidden");
    this.warningsTarget.innerHTML = warnings.map(warning => `<p>${this.escapeHtml(warning)}</p>`).join("");
  }

  hideWarnings() {
    this.warningsTarget.classList.add("hidden");
    this.warningsTarget.innerHTML = "";
  }

  renderMetadata(payload) {
    const hash = payload.sha256 ? `${payload.sha256.slice(0, 10)}…` : "none";
    this.metadataTarget.innerHTML = `
      <div><span>Template</span><strong>${this.escapeHtml(payload.spec?.style || "base")}</strong></div>
      <div><span>Size</span><strong>${payload.width} x ${payload.height}</strong></div>
      <div><span>Type</span><strong>${this.escapeHtml(payload.content_type || "")}</strong></div>
      <div><span>Hash</span><strong title="${this.escapeHtml(payload.sha256 || "")}">${hash}</strong></div>
    `;
  }

  exportPayload(payload) {
    return {
      filename: `osig-${payload.spec?.style || "image"}.${payload.extension || "png"}`,
      content_type: payload.content_type,
      width: payload.width,
      height: payload.height,
      byte_size: payload.byte_size,
      sha256: payload.sha256,
      image_base64: payload.image_base64,
    };
  }

  async copyExport() {
    if (!this.exportTarget.value) {
      return;
    }

    await navigator.clipboard.writeText(this.exportTarget.value);
    this.copyButtonTarget.textContent = "Copied";
    setTimeout(() => {
      this.copyButtonTarget.textContent = "Copy payload";
    }, 1600);
  }

  async copyField(event) {
    const sourceId = event.currentTarget.dataset.copySource;
    const source = document.getElementById(sourceId);
    if (!source) {
      return;
    }

    await navigator.clipboard.writeText(source.value);
    const originalText = event.currentTarget.textContent;
    event.currentTarget.textContent = "Copied";
    setTimeout(() => {
      event.currentTarget.textContent = originalText;
    }, 1600);
  }

  downloadImage() {
    if (!this.latestPayload?.data_uri) {
      return;
    }

    const link = document.createElement("a");
    link.href = this.latestPayload.data_uri;
    link.download = `osig-${this.latestPayload.spec?.style || "image"}.${this.latestPayload.extension || "png"}`;
    link.click();
  }

  csrfToken() {
    return this.formTarget.querySelector("input[name='csrfmiddlewaretoken']")?.value || "";
  }

  setStatus(status) {
    this.statusTarget.textContent = status;
  }

  escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}
