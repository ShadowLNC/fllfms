// Requires https://github.com/szimek/signature_pad
function padsetup() {

    var queryset = document.querySelectorAll(".signature-pad");
    var padset = [];
    for (let wrapper of queryset) {

        // Create a SignaturePad object and extend with attributes and methods.
        var canvas = wrapper.querySelector("canvas");
        var pad = new SignaturePad(canvas, {
            penColor: "blue",
        });
        pad.wrapper = wrapper;
        pad.input = wrapper.querySelector("input");
        pad.overlay = wrapper.querySelector("div").querySelector("div");
        pad.lock = function() {
            pad.overlay.style.display = "flex";
            pad.off();
            pad.fromDataURL("data:image/png;base64," + pad.input.value);
        };
        pad.unlock = function() {
            pad.overlay.style.display = "none";
            pad.clear();
            pad.input.value = "";
            pad.on();
        };
        // "When the pad is updated"
        pad.onEnd = function() {
            if (pad.isEmpty()) {
                pad.input.value = "";
            } else {
                // cut data:image/png;base64,
                pad.input.value = this.toDataURL().substring(22);
            }
        };
        pad._canvasResize = function () {
            // Adapted from https://github.com/szimek/signature_pad
            // This is abstracted from resize() as we need it in the setup.
            pad.dimensions = pad.getDimensions();  // Make sure to update.
            pad.canvas.width = pad.dimensions.width * pad.dimensions.ratio;
            pad.canvas.height = pad.dimensions.height * pad.dimensions.ratio;
            pad.canvas.getContext("2d").scale(
                pad.dimensions.ratio, pad.dimensions.ratio);
            pad.clear();  // Otherwise fromDataURL and isEmpty mightn't work.
        };
        pad.resize = function () {
            if (!pad.dimensions.isEqual(pad.getDimensions())) {
                pad.onEnd();  // Store current value to input.
                pad._canvasResize();
                pad.lock();  // _canvasResize clears but this will restore it.
            }
        };
        pad.getDimensions = function () {
            // Basic set of dimensions for the canvas.
            return {
                width: pad.canvas.offsetWidth,
                height: pad.canvas.offsetHeight,
                ratio: Math.max(window.devicePixelRatio || 1, 1),
                isEqual: function (cmp) {
                    // Basic comparison as objects will never be equal by ref.
                    return (this.width == cmp.width &&
                        this.height == cmp.height &&
                        this.ratio == cmp.ratio);
                }
            };
        };

        // Finish setup and apply loaded data, if present.
        pad._canvasResize();
        if (pad.input.value) {
            pad.lock();  // If previously signed, lock (and load input).
        }
        wrapper.querySelector("button").addEventListener("click", pad.unlock);

        // Finally, add pad to list of all signature pads on the page.
        padset.push(pad);
    }

    window.addEventListener("resize", function() {
        for (let pad of padset) {
            pad.resize();
        }
    });

}

window.addEventListener("load", padsetup);
