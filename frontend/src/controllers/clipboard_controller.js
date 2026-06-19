import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["source", "button", "status"];

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
    if (!text) {
      return false;
    }

    const copyBuffer = document.createElement("textarea");
    copyBuffer.value = text;
    copyBuffer.readOnly = true;
    copyBuffer.tabIndex = -1;
    copyBuffer.style.position = "fixed";
    copyBuffer.style.insetInlineStart = "-9999px";
    copyBuffer.style.top = "0";
    copyBuffer.style.opacity = "0";
    document.body.appendChild(copyBuffer);
    copyBuffer.select();

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
      copyBuffer.remove();
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
    if (!this.hasButtonTarget && !this.hasStatusTarget) {
      return;
    }

    if (this.hasButtonTarget) {
      this.buttonTarget.textContent = text;
    }
    if (this.hasStatusTarget) {
      this.statusTarget.textContent = text;
    }
    this.clearResetTimer();
    this.resetTimer = window.setTimeout(() => {
      if (this.hasButtonTarget) {
        this.buttonTarget.textContent = this.defaultButtonText || "Copy";
      }
      if (this.hasStatusTarget) {
        this.statusTarget.textContent = "";
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
