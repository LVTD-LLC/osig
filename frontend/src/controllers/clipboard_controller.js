import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["source", "button"];

  connect() {
    if (this.hasButtonTarget) {
      this.defaultButtonText = this.buttonTarget.textContent.trim();
    }
  }

  disconnect() {
    this.clearResetTimer();
  }

  async copy() {
    const text = this.sourceText();

    if (!text) {
      this.showFailedState();
      return;
    }

    try {
      await navigator.clipboard.writeText(text);
      this.showCopiedState();
    } catch (error) {
      if (!this.fallbackCopy(text)) {
        console.error("Failed to copy text", error);
        this.showFailedState();
      }
    }
  }

  sourceText() {
    if (!this.hasSourceTarget) {
      return "";
    }

    return (this.sourceTarget.value || this.sourceTarget.textContent || "").trim();
  }

  fallbackCopy(text) {
    if (!this.hasSourceTarget || !text) {
      return false;
    }

    this.sourceTarget.focus();
    this.sourceTarget.select();

    try {
      if (!document.execCommand("copy")) {
        throw new Error("Copy command was not accepted");
      }
      this.showCopiedState();
      return true;
    } catch (error) {
      console.error("Failed to copy text", error);
      return false;
    } finally {
      window.getSelection()?.removeAllRanges();
    }
  }

  showCopiedState() {
    this.showButtonState("Copied");
  }

  showFailedState() {
    this.showButtonState("Copy failed");
  }

  showButtonState(text) {
    if (!this.hasButtonTarget) {
      return;
    }

    this.buttonTarget.textContent = text;
    this.clearResetTimer();
    this.resetTimer = window.setTimeout(() => {
      if (this.hasButtonTarget) {
        this.buttonTarget.textContent = this.defaultButtonText || "Copy";
      }
      this.resetTimer = null;
    }, 2000);
  }

  clearResetTimer() {
    if (this.resetTimer) {
      window.clearTimeout(this.resetTimer);
      this.resetTimer = null;
    }
  }
}
