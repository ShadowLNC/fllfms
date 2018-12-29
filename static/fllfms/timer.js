//jshint-esversion: 6

class Timer {
    constructor(element) {
        this.starttime = 0; // Wall-clock time (usec) when start command received.
        this.initelapsed = 0; // Initial elapsed time (usec) when start command received.
        this._stage = {
            index: -1,
            trigger: 0,
            css: "",
            display: 0,
            sound: null,
        };
        this._profile = null;  // TODO needed or not?
        this.element = element;
        this.interval = null;
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

        // TODO don't update if not necessary.

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

        this._profile = profile;
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

    get elapsed() {
        return (Date.now()*1000 - this.starttime) + this.initelapsed;
    }

    redraw() {
        // Get elapsed time in this stage, subtract it from the stage display value.
        let display = this.elapsed - this.stage.trigger;
        display = this.stage.display - display;
        display = Math.max(Math.ceil(display/1000000), 0);  // Minimum limit 0.

        // Set display based on format. TODO
        this.element.innerHTML = display;
    }

    statechange(data) {
        let action = "start"; // todo
        switch (action) {
            case "prestart":
                this.prestart();
                break;
            case "start":
                this.start();
                break;
            case "end":
                // This will rarely occur.
                this.end();
                break;
            case "abort":
            default:
                // If an unknown state is encountered, we also abort.
                this.abort();
                break;
        }
    }

    prestart() {
        this.stopinterval();  // Should already have stopped, really.
        this.stage = this.profile.prestartstage;
    }
    start() {
        this.starttime = Date.now()*1000;  // Convert msec to usec.
        this.initelapsed = 0; // todo
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
        let stages = this.profile.stages;
        let index = this.stage.index;
        while (++index < stages.length && this.elapsed >= stages[index].trigger) {
            this.stage = stages[index];
        }

        // Redraw (occasionally superfluous if stage has changed).
        this.redraw();
    }
}
