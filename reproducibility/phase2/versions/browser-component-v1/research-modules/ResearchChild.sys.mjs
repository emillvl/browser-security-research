export class ResearchChild extends JSWindowActorChild {
  async handleEvent(event) {
    try {
      if (typeof event.detail !== "string" || event.detail.length > 8192) return;
      const request = JSON.parse(event.detail);
      const response = await this.sendQuery("Execute", { op: request.op, input: request.input });
      const win = this.contentWindow;
      win.dispatchEvent(
        new win.CustomEvent("ResearchResult", {
          detail: JSON.stringify({ id: request.id, response }),
        }),
      );
    } catch (error) {
      const win = this.contentWindow;
      win.dispatchEvent(
        new win.CustomEvent("ResearchResult", { detail: JSON.stringify({ error: error.message }) }),
      );
    }
  }
}
