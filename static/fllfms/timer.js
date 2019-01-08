// jshint esversion: 6
const TIMERSTATES = {
    // NOTE: Keep this synchronised with models.py.
    PRESTART: 0,
    START: 1,
    END: 2,
    ABORT: 3,
};

class Timer {
    constructor(timerid, element) {
        this.timerid = timerid;
        this.element = element;  // Timer DOM element for updating.
        this.interval = null;  // Timer redraw interval ID, if running.

        this._stage = {
            // Timer stage ("state") pulled from the profile.
            // Pretty sure this will always be overriden before it's used, but keeping it for safety.
            index: -1,
            trigger: 0,
            css: "",
            display: 0,
            sound: null,
        };
        this._profile = null;  // Schema for css and sounds based on timer state.
        this._action = null;  // Last timer action command received.

        this.msgqueue = [];
        this.socket = null;
        this.socketfailures = 0;  // Failures since last success.
        this.mksocket();
    }

    get profile() {
        return this._profile;
    }

    set profile(data) {
        function makeSound(file) {
            if (file) {
                return new Audio(file);
            }
            return null;
        }

        // This assumes that profile stages are sorted based on trigger.
        data.stages.unshift({
            index: 0,
            trigger: 0,
            css: data.startcss,
            display: data.startdisplay || data.duration,
            sound: makeSound(data.startsound),
        });
        for (let i=1; i<data.stages.length; ++i) {
            let prev = data.stages[i-1];
            let stage = data.stages[i];
            stage.index = i;
            stage.css = stage.css || prev.css;
            // Fallback display: use the previous display, minus the length
            // of the previous stage. (prev.display - (stage.trigger - prev.trigger))
            stage.display = stage.display || (prev.display + prev.trigger - stage.trigger);
            stage.sound = makeSound(stage.sound);
        }

        let profile = {
            format: data.format,
            duration: data.duration,
            stages: data.stages,
            prestartstage: {
                index: -1,
                trigger: 0,
                css: data.prestartcss,
                display: 0,
                sound: null,
            },
            endstage: {
                index: -1,
                trigger: 0,
                css: data.endcss,
                display: 0,
                sound: makeSound(data.endsound),
            },
            abortstage: {
                index: -1,
                trigger: 0,
                css: data.endcss,
                display: 0,
                sound: makeSound(data.abortsound),
            },
        };

        /*
         * First, we must stop any interval, as old stage indices may be out of
         * bounds, so dointerval() would throw exceptions with the new profile.
         *
         * After the new profile is installed, we rerun the last action,
         * restarting the interval where appropriate and setting the stage
         * based on the new profile.
         *
         * During initialisation, the action may be received first, but cannot
         * run, as it will not have a profile to set stages from. This is also
         * solved by rerunning the last action here. If the profile is received
         * first (before any action), action will be null, and won't be rerun.
         */
        this.stopinterval();
        this._profile = profile;
        if (this.action != null) {
            this.action = this.action;
        }
    }

    get stage() {
        return this._stage;
    }

    set stage(newstage) {
        // Update stage.
        this.element.className = newstage.css;
        if (newstage.sound != null) {
            newstage.sound.play();
        }
        this._stage = newstage;
        this.redraw();  // Update time value.
    }

    get action() {
        return this._action;
    }

    set action(newaction) {
        this._action = newaction;
        if (this.profile != null) {
            /*
             * We can only do this if the profile is present, or else there
             * will not be any stages to use. When the profile is set, it will
             * rerun this, setting the new profile.
             *
             * A race condition could cause this to run more than once (during
             * initialisation only), but it will not have any adverse effects.
             */
            switch (this._action.state) {
                case TIMERSTATES.PRESTART:
                    this.prestart();
                    break;
                case TIMERSTATES.START:
                    this.start();
                    break;
                case TIMERSTATES.END:
                    this.end();
                    break;
                case TIMERSTATES.ABORT:
                default:
                    // If an unknown state is encountered, we also abort.
                    this.abort();
                    break;
            }
        }
    }

    get elapsed() {
        // Rather than Date.now(), we use (new Event(null)).timeStamp, since
        // Event.timeStamp could be either DOMHighResTimeStamp or Date (browser dependent).
        // If DOMHighResTimeStamp, this appears to be the simplest way to get it.
        return (new Event(null)).timeStamp*1000 - this.action.timestamp;
    }

    prestart() {
        this.stopinterval();  // Should already have stopped, really.
        this.stage = this.profile.prestartstage;
    }

    start() {
        this.prestart();  // Reset to prestart stage, resetting stage index.
        this.startinterval();
    }

    end() {
        // Apply end state, revoke interval.
        this.stopinterval();
        this.stage = this.profile.endstage;
    }

    abort() {
        this.stopinterval();
        this.stage = this.profile.abortstage;
    }

    startinterval() {
        // Prevent multiple intervals from being run for one timer.
        if (this.interval == null) {
            this.interval = setInterval(this.dointerval.bind(this), 50);
            this.dointerval();
        }
    }

    stopinterval() {
        clearInterval(this.interval);
        this.interval = null;
    }

    dointerval() {
        // This interval only executes when the timer is running.
        if (this.elapsed > this.profile.duration) {
            this.end();
            return;
        }

        // Move to new stage if one exists, and trigger has occurred.
        // This assumes that profile stages are sorted based on trigger.
        let stages = this.profile.stages;
        let index = this.stage.index;
        while (++index < stages.length && this.elapsed >= stages[index].trigger) {
            this.stage = stages[index];
        }

        // Redraw (occasionally superfluous if stage has changed).
        this.redraw();
    }

    redraw() {
        // Get elapsed time in this stage, subtract it from the stage display value.
        let display = this.elapsed - this.stage.trigger;
        display = this.stage.display - display;
        display = Math.max(Math.ceil(display/1000000), 0);  // Minimum limit 0.

        // Set display based on format.
        if (this.profile.format) {
            // Display as minutes:seconds.
            display = parseInt(display / 60).toString() + ":" + (display % 60).toString().padStart(2, "0");
        } else {
            // Just seconds.
            display = display.toString();
        }
        this.element.textContent = display;
    }

    mksocket() {
        if (this.socket != null && [0, 1].includes(this.socket.readyState)) {
            // Socket exists and is either CONNECTING (0) or OPEN (1).
            return;
        }
        let protocol = "ws" + window.location.protocol.slice(4) + "//";
        // Hardcoding the path is far from ideal, but it's the easiest solution.
        let path = "/websocket/timercontrol/" + this.timerid + "/";
        this.socket = new WebSocket(protocol + window.location.host + path);
        this.socket.addEventListener('open', this.socketopen.bind(this));
        this.socket.addEventListener('message', this.socketmessage.bind(this));
        this.socket.addEventListener('close', this.socketclose.bind(this));
        this.socket.addEventListener('error', this.socketerror.bind(this));
    }

    socketmessage(event) {
        let data = JSON.parse(event.data);
        // We will get either a profile, state, or match event.
        switch (data.type) {
            case "profile":
                this.profile = data;
                break;
            case "state":
                // Calculate the wall-clock time (usec) the action (state change) actually occurred.
                data.timestamp = parseInt(event.timeStamp*1000);
                if (data.elapsed != undefined) {
                    // Typically only defined for "start" where elapsed time matters.
                    data.timestamp -= data.elapsed;
                }
                this.action = data;
                break;
            case "match":
                // TODO
                break;
            default:
                break;
        }
    }

    socketopen(event) {
        console.info("WebSocket connected.");
        this.socketfailures = 0;  // Reset the failure count.
        let queue = this.msgqueue;
        this.msgqueue = [];  // Clear queue.

        // Setup the socket by subscribing to the relevant events.
        let subs = ["profile", "state", "match"];
        for (let subscription of subs) {
            this.request({
                type: "subscribe",
                channel: subscription,
            });
        }

        // Dispatch any pending requests.
        for (let msg of queue) {
            this.request(msg);
        }
    }

    socketclose(event) {
        const SOCKET_NORMAL_CLOSE = 1000;  // Includes page refresh on Firefox.
        const SOCKET_DO_NOT_REOPEN = 4999;  // As defined by FLLFMS.
        const NO_RETRIES = [];  // Any other codes that we shouldn't retry.
        const MAX_FAILURES = 3;
        let retry = ! NO_RETRIES.includes(event.code);  // Do not retry (e.g. logout).

        if (event.code == SOCKET_NORMAL_CLOSE) {
            // NOTE: Firefox will display this in the console of the next page.
            console.info("WebSocket closed normally (code 1000), not retrying.");
        }
        else if (event.code == SOCKET_DO_NOT_REOPEN) {
            console.error("WebSocket forcibly closed by server (DO_NOT_REOPEN). Reloading...");
            window.location.reload();
        }
        else if (retry && ++this.socketfailures <= MAX_FAILURES) {
            console.warn(
                "WebSocket connection lost (code " + event.code + "). " +
                "Reconnecting... (attempt " + this.socketfailures + "/" + MAX_FAILURES + ")");
            setTimeout(this.mksocket.bind(this), 1000);
        }
        else {
            console.error("WebSocket connection lost. Refresh page to retry.");
            // Should probably do something here to improve UX.
            alert("WebSocket could not connect.\n" +
                  "Maybe your network doesn't support WebSockets?\n" +
                  "Refresh page to try again.");
        }
    }

    socketerror(event) {
        // Log the error, might be useful for diagnostics.
        // Not much we can do; if socket closes, we handle that insted.
        console.error("WebSocket Error", event);
    }

    request(payload) {
        // Send JSON data to the socket, if readyState == 1 (open).
        if (this.socket != null && this.socket.readyState == 1) {
            this.socket.send(JSON.stringify(payload));
        } else {
            this.msgqueue.push(payload);
        }
    }

    requestmatch(next=true) {
        this.request({
            type: "set",
            channel: "match",
            next: next,
        });
    }

    requestaction(action) {
        this.request({
            type: "set",
            channel: "state",
            action: action,
        })
    }

}
