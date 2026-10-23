import { Broker } from "./Broker.sys.mjs";
export class ResearchParent extends JSWindowActorParent {
  async receiveMessage(message) {
    if (message.name !== "Execute") return { error: "Unknown actor message" };
    return Broker.run(
      message.data,
      this.manager.documentPrincipal.originNoSuffix,
      this.browsingContext.parent !== null,
    );
  }
}
