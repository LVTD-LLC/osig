import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["source", "button"];

  connect() {
    if (this.hasButtonTarget) {
      this.defaultButtonText = this.buttonTarget.textContent.trim();
    }
  }

  async copy() {
    const text = this.sourceText();

    try {
      await navigator.clipboard.writeText(text);
      this.showCopiedState();
    } catch (error) {
      this.fallbackCopy();
    }
  }

  sourceText() {
    if (!this.hasSourceTarget) {
      return "";
    }

    return (this.sourceTarget.value || this.sourceTarget.textContent || "").trim();
  }

  fallbackCopy() {
    if (!this.hasSourceTarget) {
      return;
    }

    this.sourceTarget.focus();
    this.sourceTarget.select();

    try {
      if (!document.execCommand("copy")) {
        throw new Error("Copy command was not accepted");
      }
      this.showCopiedState();
    } catch (error) {
      console.error("Failed to copy text", error);
    }

    window.getSelection()?.removeAllRanges();
  }

  showCopiedState() {
    if (!this.hasButtonTarget) {
      return;
    }

    this.buttonTarget.textContent = "Copied";
    window.setTimeout(() => {
      this.buttonTarget.textContent = this.defaultButtonText || "Copy";
    }, 2000);
  }
}
