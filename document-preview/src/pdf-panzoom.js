import panzoom from "upstream-panzoom";

export default function pdfPanzoom(scene, options) {
  const controller = panzoom(scene, options);
  const viewport = scene.parentElement;
  // Panzoom consumes single-finger swipes even at 1x. Let a multipage
  // document use native scrolling; keep pinch and zoomed panning intact.
  const scrollAtDefaultZoom = (event) => {
    if (
      event.touches.length === 1 &&
      viewport.scrollHeight > viewport.clientHeight + 1 &&
      Math.abs(controller.getTransform().scale - 1) < 0.01
    ) {
      event.stopImmediatePropagation();
    }
  };
  viewport.addEventListener("touchstart", scrollAtDefaultZoom, {
    capture: true,
    passive: true,
  });
  const dispose = controller.dispose;
  controller.dispose = () => {
    viewport.removeEventListener("touchstart", scrollAtDefaultZoom, {
      capture: true,
    });
    dispose();
  };
  return controller;
}
