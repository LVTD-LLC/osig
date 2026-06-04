import { Controller } from "@hotwired/stimulus";

const FORM_STEP_COUNT = 5;

export default class extends Controller {
  static targets = [
    "step",
    "pageUrl",
    "title",
    "subtitle",
    "eyebrow",
    "site",
    "style",
    "font",
    "imageUrl",
    "format",
    "quality",
    "maxKb",
    "version",
    "metaTags",
    "validationLinks",
    "previewLink",
    "errorMessage",
    "wizardForm",
    "progressItem",
  ];

  connect() {
    this.currentStep = 0;
    this.updateStepVisibility();
    if (this.hasPageUrlTarget) {
      this.pageUrlTarget.value = `${window.location.origin}`;
    }
  }

  goNext() {
    if (this.currentStep < FORM_STEP_COUNT - 1) {
      this.currentStep += 1;
      this.updateStepVisibility();
    }
  }

  goPrevious() {
    if (this.currentStep > 0) {
      this.currentStep -= 1;
      this.updateStepVisibility();
    }
  }

  updateStepVisibility() {
    this.stepTargets.forEach((step, index) => {
      step.classList.toggle("hidden", index !== this.currentStep);
    });

    this.progressItemTargets.forEach((item, index) => {
      item.classList.toggle("is-active", index === this.currentStep);
    });

    if (this.hasErrorMessageTarget) {
      this.errorMessageTarget.textContent = "";
    }
  }

  async generate(event) {
    event.preventDefault();
    this.clearError();
    this.disableButtons(true);

    try {
      const payload = this.buildPayload();

      const response = await fetch("/api/onboarding/meta", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Unable to generate onboarding artifacts.");
      }

      const data = await response.json();
      this.metaTagsTarget.value = data.meta_tags;
      this.previewLinkTarget.href = data.signed_url;
      this.previewLinkTarget.classList.remove("hidden");
      this.previewLinkTarget.removeAttribute("aria-disabled");
      this.renderValidationLinks(data.validation_links);
    } catch (error) {
      this.setError(error.message || "Unable to generate onboarding artifacts.");
    } finally {
      this.disableButtons(false);
    }
  }

  async copyMetaTags() {
    try {
      await navigator.clipboard.writeText(this.metaTagsTarget.value);
    } catch (error) {
      this.setError("Failed to copy meta tags.");
      console.error("Failed to copy meta tags", error);
    }
  }

  reset() {
    this.wizardFormTarget.reset();
    this.currentStep = 0;
    this.metaTagsTarget.value = "";
    this.previewLinkTarget.href = "#";
    this.previewLinkTarget.classList.add("hidden");
    this.previewLinkTarget.setAttribute("aria-disabled", "true");
    this.validationLinksTarget.innerHTML = "";
    this.clearError();
    this.updateStepVisibility();
  }

  buildPayload() {
    if (!this.pageUrlTarget.value.trim()) {
      throw new Error("Please provide a canonical page URL.");
    }

    if (!this.titleTarget.value.trim()) {
      throw new Error("Please provide a title.");
    }

    const qualityValue = Number.parseInt(this.qualityTarget.value, 10);

    const payload = {
      page_url: this.pageUrlTarget.value.trim(),
      style: this.styleTarget.value,
      site: this.siteTarget.value,
      font: this.fontTarget.value,
      title: this.titleTarget.value.trim(),
      subtitle: this.subtitleTarget.value.trim(),
      eyebrow: this.eyebrowTarget.value.trim(),
      image_url: this.imageUrlTarget.value.trim(),
      format: this.formatTarget.value,
      version: this.versionTarget.value.trim(),
      expires_in_seconds: 3600,
    };

    const maxKbValue = Number.parseInt(this.maxKbTarget.value, 10);

    if (Number.isInteger(qualityValue) && qualityValue > 0 && qualityValue <= 100) {
      payload.quality = qualityValue;
    }

    if (Number.isInteger(maxKbValue) && maxKbValue > 0) {
      payload.max_kb = maxKbValue;
    }

    return payload;
  }

  renderValidationLinks(validationLinks) {
    this.validationLinksTarget.innerHTML = "";

    Object.entries(validationLinks).forEach(([name, href]) => {
      const link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = "btn-secondary min-h-0 px-3 py-2";
      link.textContent = name;

      this.validationLinksTarget.appendChild(link);
    });
  }

  setError(message) {
    if (this.hasErrorMessageTarget) {
      this.errorMessageTarget.textContent = message;
    }
  }

  clearError() {
    if (this.hasErrorMessageTarget) {
      this.errorMessageTarget.textContent = "";
    }
  }

  disableButtons(disabled) {
    this.stepTargets.forEach((step) => {
      step.querySelectorAll("button").forEach((button) => {
        button.disabled = disabled;
        button.classList.toggle("opacity-50", disabled);
      });
    });
  }
}
