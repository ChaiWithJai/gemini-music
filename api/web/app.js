const VIDEO_ID = "lZXeUhUc8PM";
const GOLDEN_PROFILE = "maha_mantra_v1";

const STAGE_IDS = {
  listen: "stage-listen",
  guided: "stage-guided",
  call_response: "stage-call",
  recap: "stage-recap",
  independent: "stage-independent",
};

const STAGE_BUTTON_IDS = {
  listen: "listenBtn",
  guided: "guidedBtn",
  call_response: "callResponseBtn",
  recap: "recapBtn",
  independent: "independentBtn",
};

const STAGE_ORDER = ["listen", "guided", "call_response", "recap", "independent"];

const STAGE_COPY = {
  listen: {
    title: "Listen (30s)",
    now: "You're here: absorb pronunciation and cadence.",
    next: "Next in 45s guided follow-along.",
    lock: "Why locked: initialize a session first.",
  },
  guided: {
    title: "Guided Follow-Along",
    now: "You're here: sing with the track and capture metrics.",
    next: "Next: alternate guru and student turns.",
    lock: "Why locked: complete Listen first.",
  },
  call_response: {
    title: "Call-Response",
    now: "You're here: take your turn when guru audio mutes.",
    next: "Next: inspect recap before solo performance.",
    lock: "Why locked: complete Guided first.",
  },
  recap: {
    title: "Performance Recap",
    now: "You're here: review scorecards and feedback.",
    next: "Next: start independent chanting.",
    lock: "Why locked: complete Call-Response first.",
  },
  independent: {
    title: "Independent Performance",
    now: "You're here: perform solo for final scoring and Bhav.",
    next: "Next: flow complete.",
    lock: "Why locked: view recap first.",
  },
};

const STAGE_TITLES = {
  guided: "Guided Follow-Along",
  call_response: "Call-Response",
  independent: "Independent Performance",
};

const state = {
  player: null,
  playerReady: false,
  userId: null,
  sessionId: null,
  lineage: "vaishnavism",
  currentStage: "idle",
  callPhase: "-",
  stageResults: {},
  finalArtifacts: {},
  busy: false,
  mediaMode: "youtube",
  mediaMuted: false,
  fallbackAudioCtx: null,
  fallbackMasterGain: null,
  fallbackNodes: [],
  queueEventKey: null,
};

const els = {
  displayName: document.getElementById("displayName"),
  lineageSelect: document.getElementById("lineageSelect"),
  initSessionBtn: document.getElementById("initSessionBtn"),
  sessionMeta: document.getElementById("sessionMeta"),
  currentStageLabel: document.getElementById("currentStageLabel"),
  turnLabel: document.getElementById("turnLabel"),
  countdownLabel: document.getElementById("countdownLabel"),
  micStatus: document.getElementById("micStatus"),
  listenBtn: document.getElementById("listenBtn"),
  guidedBtn: document.getElementById("guidedBtn"),
  callResponseBtn: document.getElementById("callResponseBtn"),
  recapBtn: document.getElementById("recapBtn"),
  independentBtn: document.getElementById("independentBtn"),
  queueNowTitle: document.getElementById("queueNowTitle"),
  queueNowCopy: document.getElementById("queueNowCopy"),
  queueNextTitle: document.getElementById("queueNextTitle"),
  queueNextCopy: document.getElementById("queueNextCopy"),
  queueLaterCopy: document.getElementById("queueLaterCopy"),
  queuePrimaryBtn: document.getElementById("queuePrimaryBtn"),
  mediaStatus: document.getElementById("mediaStatus"),
  useFallbackBtn: document.getElementById("useFallbackBtn"),
  retryYoutubeBtn: document.getElementById("retryYoutubeBtn"),
  playerContainer: document.getElementById("player"),
  resultsContainer: document.getElementById("resultsContainer"),
  finalJson: document.getElementById("finalJson"),
};

let playerReadyResolver = null;
const playerReadyPromise = new Promise((resolve) => {
  playerReadyResolver = resolve;
});

window.onYouTubeIframeAPIReady = function onYouTubeIframeAPIReady() {
  state.player = new YT.Player("player", {
    videoId: VIDEO_ID,
    playerVars: {
      controls: 1,
      rel: 0,
      modestbranding: 1,
      playsinline: 1,
    },
    events: {
      onReady: () => {
        state.playerReady = true;
        setMediaStatus("Media mode: YouTube");
        if (playerReadyResolver) {
          playerReadyResolver();
        }
      },
      onError: () => {
        setMediaStatus("YouTube playback blocked. Switching to fallback track.");
        switchToFallbackTrack("YouTube error callback").catch((err) => {
          console.warn("fallback handoff failed", err);
        });
      },
    },
  });
};

function setStageLabel(label) {
  els.currentStageLabel.textContent = label;
}

function setTurn(label) {
  els.turnLabel.textContent = label;
}

function setCountdown(label) {
  els.countdownLabel.textContent = label;
}

function setMicStatus(label) {
  const textEl = els.micStatus.querySelector(".mic-text");
  if (textEl) {
    textEl.textContent = `Mic: ${label}`;
  }
  if (label === "capturing") {
    els.micStatus.classList.add("capturing");
  } else {
    els.micStatus.classList.remove("capturing");
  }
}

function setActiveStage(stageKey) {
  Object.values(STAGE_IDS).forEach((id) => {
    document.getElementById(id).classList.remove("active");
  });
  if (STAGE_IDS[stageKey]) {
    document.getElementById(STAGE_IDS[stageKey]).classList.add("active");
  }
  state.currentStage = stageKey;
  updateNavDots();
  updateInteractionQueue();
}

function markStageDone(stageKey) {
  if (STAGE_IDS[stageKey]) {
    document.getElementById(STAGE_IDS[stageKey]).classList.add("done");
  }
  syncStageCtaLabels();
  updateNavDots();
  updateInteractionQueue();
}

function getStageButton(stageKey) {
  const id = STAGE_BUTTON_IDS[stageKey];
  if (!id) {
    return null;
  }
  return document.getElementById(id);
}

function setMediaStatus(message) {
  if (els.mediaStatus) {
    els.mediaStatus.textContent = message;
  }
}

function setMediaMode(mode) {
  state.mediaMode = mode;
  if (els.playerContainer) {
    els.playerContainer.classList.toggle("fallback-active", mode === "fallback");
  }
  if (els.retryYoutubeBtn) {
    els.retryYoutubeBtn.disabled = mode !== "fallback";
  }
  if (els.useFallbackBtn) {
    els.useFallbackBtn.disabled = mode === "fallback";
  }
}

function syncStageCtaLabels() {
  STAGE_ORDER.forEach((stageKey) => {
    const btn = getStageButton(stageKey);
    if (!btn) {
      return;
    }
    const stageEl = document.getElementById(STAGE_IDS[stageKey]);
    const done = Boolean(stageEl && stageEl.classList.contains("done"));
    const startLabel = btn.dataset.startLabel || btn.textContent.trim();
    const replayLabel = btn.dataset.replayLabel || `Replay ${startLabel}`;
    btn.textContent = done ? replayLabel : startLabel;
  });
}

function computeQueueState() {
  const statuses = {};
  STAGE_ORDER.forEach((stageKey) => {
    const stageEl = document.getElementById(STAGE_IDS[stageKey]);
    const btn = getStageButton(stageKey);
    if (stageEl && stageEl.classList.contains("done")) {
      statuses[stageKey] = "done";
      return;
    }
    if (btn && btn.dataset.enabled === "true") {
      statuses[stageKey] = "ready";
      return;
    }
    statuses[stageKey] = "locked";
  });

  const busyNow = state.busy && STAGE_ORDER.includes(state.currentStage) ? state.currentStage : null;
  const readyNow = STAGE_ORDER.find((stageKey) => statuses[stageKey] === "ready") || null;
  const nowKey = busyNow || readyNow;
  const allDone = STAGE_ORDER.every((stageKey) => statuses[stageKey] === "done");

  const startIndex = nowKey ? STAGE_ORDER.indexOf(nowKey) + 1 : 0;
  const nextKey = STAGE_ORDER.slice(startIndex).find((stageKey) => statuses[stageKey] !== "done") || null;
  const laterKeys = STAGE_ORDER.filter((stageKey) => statuses[stageKey] === "locked");

  return {
    statuses,
    nowKey,
    nextKey,
    laterKeys,
    allDone,
  };
}

function setQueuePrimaryAction(action, label, disabled) {
  if (!els.queuePrimaryBtn) {
    return;
  }
  els.queuePrimaryBtn.dataset.action = action || "";
  els.queuePrimaryBtn.textContent = label;
  els.queuePrimaryBtn.disabled = disabled;
}

function emitQueueTelemetry(snapshot) {
  if (!state.sessionId) {
    return;
  }
  const payload = {
    now: snapshot.nowKey,
    next: snapshot.nextKey,
    later: snapshot.laterKeys,
    statuses: snapshot.statuses,
    media_mode: state.mediaMode,
  };
  const key = JSON.stringify(payload);
  if (state.queueEventKey === key) {
    return;
  }
  state.queueEventKey = key;
  api(`/v1/sessions/${state.sessionId}/events`, {
    method: "POST",
    body: JSON.stringify({
      event_type: "interaction_queue_state",
      client_event_id: `queue:${Date.now()}`,
      payload,
    }),
  }).catch((err) => {
    console.warn("interaction queue telemetry failed", err);
  });
}

function updateInteractionQueue() {
  if (!els.queuePrimaryBtn) {
    return;
  }

  if (!state.sessionId) {
    els.queueNowTitle.textContent = "Initialize Session";
    els.queueNowCopy.textContent = "You're here. Start a session to unlock the guided queue.";
    els.queueNextTitle.textContent = STAGE_COPY.listen.title;
    els.queueNextCopy.textContent = STAGE_COPY.listen.next;
    els.queueLaterCopy.textContent = "Why locked: complete setup before guided practice.";
    setQueuePrimaryAction("init", "Initialize Session", state.busy || els.initSessionBtn.disabled);
    return;
  }

  const snapshot = computeQueueState();
  if (snapshot.allDone) {
    els.queueNowTitle.textContent = "Flow Complete";
    els.queueNowCopy.textContent = "You're here. Review output or replay any completed stage.";
    els.queueNextTitle.textContent = "Start New Session";
    els.queueNextCopy.textContent = "Next: initialize another practice run.";
    els.queueLaterCopy.textContent = "Why locked: none. All stages are complete.";
    setQueuePrimaryAction("init", "Start New Session", state.busy);
    emitQueueTelemetry(snapshot);
    return;
  }

  if (snapshot.nowKey) {
    const nowCopy = STAGE_COPY[snapshot.nowKey];
    const nowButton = getStageButton(snapshot.nowKey);
    els.queueNowTitle.textContent = nowCopy.title;
    els.queueNowCopy.textContent = nowCopy.now;
    const actionLabel = nowButton ? (nowButton.dataset.startLabel || nowButton.textContent.trim()) : nowCopy.title;
    setQueuePrimaryAction(snapshot.nowKey, actionLabel, state.busy || !nowButton || nowButton.disabled);
  } else {
    els.queueNowTitle.textContent = "Waiting For Input";
    els.queueNowCopy.textContent = "You're here. Complete the required step to continue.";
    setQueuePrimaryAction("", "Waiting", true);
  }

  if (snapshot.nextKey) {
    const nextCopy = STAGE_COPY[snapshot.nextKey];
    els.queueNextTitle.textContent = nextCopy.title;
    els.queueNextCopy.textContent = nextCopy.next;
  } else {
    els.queueNextTitle.textContent = "No pending stage";
    els.queueNextCopy.textContent = "Next: finalize or start a new session.";
  }

  if (snapshot.laterKeys.length) {
    els.queueLaterCopy.textContent = snapshot.laterKeys.map((stageKey) => STAGE_COPY[stageKey].lock).join(" ");
  } else {
    els.queueLaterCopy.textContent = "Why locked: none.";
  }

  emitQueueTelemetry(snapshot);
}

async function ensureFallbackTrack() {
  if (state.fallbackAudioCtx && state.fallbackMasterGain) {
    return;
  }
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) {
    throw new Error("Web Audio API is unavailable; cannot start fallback track.");
  }

  const context = new AudioCtx();
  const masterGain = context.createGain();
  masterGain.gain.value = 0;
  masterGain.connect(context.destination);

  const nodes = [
    { freq: 196.0, type: "sine", level: 0.05 },
    { freq: 293.66, type: "triangle", level: 0.035 },
    { freq: 392.0, type: "sine", level: 0.02 },
  ].map((voice) => {
    const osc = context.createOscillator();
    const gain = context.createGain();
    osc.type = voice.type;
    osc.frequency.value = voice.freq;
    gain.gain.value = voice.level;
    osc.connect(gain);
    gain.connect(masterGain);
    osc.start();
    return { osc, gain };
  });

  state.fallbackAudioCtx = context;
  state.fallbackMasterGain = masterGain;
  state.fallbackNodes = nodes;
}

function setMediaMuted(muted) {
  state.mediaMuted = Boolean(muted);
  if (state.mediaMode === "fallback") {
    if (!state.fallbackAudioCtx || !state.fallbackMasterGain) {
      return;
    }
    const now = state.fallbackAudioCtx.currentTime;
    const target = state.mediaMuted ? 0 : 0.11;
    state.fallbackMasterGain.gain.cancelScheduledValues(now);
    state.fallbackMasterGain.gain.setTargetAtTime(target, now, 0.08);
    return;
  }
  if (!state.player) {
    return;
  }
  if (state.mediaMuted) {
    state.player.mute();
  } else {
    state.player.unMute();
  }
}

function stopFallbackTrack() {
  if (!state.fallbackAudioCtx || !state.fallbackMasterGain) {
    return;
  }
  const now = state.fallbackAudioCtx.currentTime;
  state.fallbackMasterGain.gain.cancelScheduledValues(now);
  state.fallbackMasterGain.gain.setTargetAtTime(0, now, 0.08);
}

async function playFallbackTrack(muted) {
  await ensureFallbackTrack();
  if (state.fallbackAudioCtx && state.fallbackAudioCtx.state === "suspended") {
    await state.fallbackAudioCtx.resume();
  }
  setMediaMode("fallback");
  setMediaMuted(muted);
}

async function switchToFallbackTrack(reason) {
  await playFallbackTrack(state.mediaMuted);
  setMediaStatus(`Media mode: Fallback track (${reason})`);
}

async function waitForYouTubePlaying(timeoutMs) {
  if (!state.player || !window.YT) {
    return false;
  }
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const playerState = state.player.getPlayerState ? state.player.getPlayerState() : null;
    if (playerState === YT.PlayerState.PLAYING) {
      return true;
    }
    await wait(200);
  }
  return false;
}

async function playYouTubeAt(seconds, muted) {
  const ready = await waitForPlayer();
  if (!ready || !state.player) {
    return false;
  }
  setMediaMode("youtube");
  stopFallbackTrack();
  setMediaMuted(muted);
  state.player.seekTo(seconds, true);
  state.player.playVideo();
  const started = await waitForYouTubePlaying(2000);
  if (!started) {
    return false;
  }
  setMediaStatus("Media mode: YouTube");
  return true;
}

function clamp01(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return 0;
  }
  return Math.max(0, Math.min(1, n));
}

function wait(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function waitForPlayer() {
  if (state.playerReady) {
    return true;
  }
  const timeout = await Promise.race([
    playerReadyPromise.then(() => false),
    wait(2000).then(() => true),
  ]);
  return !timeout;
}

async function api(path, options = {}) {
  const resp = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${text}`);
  }

  if (resp.status === 204) {
    return null;
  }
  return resp.json();
}

function scoreToRating(score) {
  const raw = Math.round(clamp01(score) * 5);
  return Math.max(1, raw);
}

function stageWeight(stage) {
  if (stage === "guided") {
    return 0.2;
  }
  if (stage === "call_response") {
    return 0.35;
  }
  return 0.45;
}

function calculateOverall(stageResults) {
  const keys = ["guided", "call_response", "independent"];
  let weighted = 0;
  let seen = 0;
  keys.forEach((k) => {
    const item = stageResults[k];
    if (item) {
      const w = stageWeight(k);
      weighted += item.composite * w;
      seen += w;
    }
  });
  if (seen <= 0) {
    return 0;
  }
  return Number((weighted / seen).toFixed(3));
}

function renderResults() {
  const ordered = ["guided", "call_response", "independent"];
  const container = els.resultsContainer;
  container.innerHTML = "";

  ordered.forEach((key, idx) => {
    const result = state.stageResults[key];
    if (!result) {
      return;
    }

    const passes = result.passes_golden;
    const card = document.createElement("article");
    card.className = "result-card";
    card.style.animationDelay = `${idx * 120}ms`;

    const header = document.createElement("div");
    header.className = "result-header";

    const title = document.createElement("span");
    title.className = "result-title";
    title.textContent = STAGE_TITLES[key];

    const badge = document.createElement("span");
    badge.className = `badge ${passes ? "pass" : "review-badge"}`;
    badge.textContent = passes ? "PASS" : "REVIEW";

    header.appendChild(title);
    header.appendChild(badge);

    const bars = document.createElement("div");
    bars.className = "score-bars";

    const metrics = [
      { label: "Discipline", cls: "discipline", value: result.discipline },
      { label: "Resonance", cls: "resonance", value: result.resonance },
      { label: "Coherence", cls: "coherence", value: result.coherence },
    ];

    metrics.forEach((m, mIdx) => {
      const row = document.createElement("div");
      row.className = "score-row";

      const lbl = document.createElement("span");
      lbl.className = "score-label";
      lbl.textContent = m.label;

      const track = document.createElement("div");
      track.className = "score-track";
      const fill = document.createElement("div");
      fill.className = `score-fill ${m.cls}`;
      track.appendChild(fill);

      const val = document.createElement("span");
      val.className = "score-value";
      val.textContent = "0.000";

      row.appendChild(lbl);
      row.appendChild(track);
      row.appendChild(val);
      bars.appendChild(row);

      animateBar(fill, clamp01(m.value) * 100, (idx * 120) + (mIdx * 80));
      animateCounter(val, m.value, 600, 3);
    });

    const composite = document.createElement("div");
    composite.className = "composite-score";
    const compLabel = document.createElement("span");
    compLabel.className = "composite-label";
    compLabel.textContent = "Composite";
    const compValue = document.createElement("span");
    compValue.className = "composite-value";
    compValue.textContent = "0.000";
    composite.appendChild(compLabel);
    composite.appendChild(compValue);
    animateCounter(compValue, result.composite, 800, 3);

    const feedbackList = document.createElement("ul");
    feedbackList.className = "result-feedback";
    if (result.feedback) {
      result.feedback.forEach((item) => {
        const li = document.createElement("li");
        li.textContent = item;
        feedbackList.appendChild(li);
      });
    }

    card.appendChild(header);
    card.appendChild(bars);
    card.appendChild(composite);
    card.appendChild(feedbackList);
    container.appendChild(card);
  });

  const overall = calculateOverall(state.stageResults);
  const payload = {
    lineage: state.lineage,
    session_id: state.sessionId,
    stage_results: state.stageResults,
    overall_composite: overall,
    final_artifacts: state.finalArtifacts,
  };
  els.finalJson.innerHTML = syntaxHighlightJson(JSON.stringify(payload, null, 2));
}

async function runCountdown(seconds, onTick) {
  let remaining = seconds;
  onTick(remaining);
  const countdownEl = els.countdownLabel;
  return new Promise((resolve) => {
    const intervalId = window.setInterval(() => {
      remaining -= 1;
      onTick(Math.max(remaining, 0));
      countdownEl.classList.remove("tick");
      void countdownEl.offsetWidth;
      countdownEl.classList.add("tick");
      if (remaining <= 0) {
        window.clearInterval(intervalId);
        resolve();
      }
    }, 1000);
  });
}

function mean(values) {
  if (!values.length) {
    return 0;
  }
  return values.reduce((acc, v) => acc + v, 0) / values.length;
}

function std(values, m) {
  if (values.length <= 1) {
    return 0;
  }
  const variance = values.reduce((acc, v) => acc + (v - m) ** 2, 0) / values.length;
  return Math.sqrt(variance);
}

function normalizeCadenceConsistency(onsets) {
  if (onsets.length <= 2) {
    return 0.7;
  }
  const intervals = [];
  for (let i = 1; i < onsets.length; i += 1) {
    intervals.push(onsets[i] - onsets[i - 1]);
  }
  const intervalMean = mean(intervals);
  if (intervalMean <= 0) {
    return 0.5;
  }
  const cv = std(intervals, intervalMean) / intervalMean;
  return clamp01(1 - (cv * 1.8));
}

function estimateCadenceBpm(onsets, durationSeconds) {
  if (onsets.length > 2) {
    const intervals = [];
    for (let i = 1; i < onsets.length; i += 1) {
      intervals.push(onsets[i] - onsets[i - 1]);
    }
    const intervalMean = mean(intervals);
    if (intervalMean > 0) {
      return 60 / intervalMean;
    }
  }
  if (durationSeconds <= 0) {
    return 72;
  }
  return (onsets.length / durationSeconds) * 60;
}

function autoCorrelatePitch(buffer, sampleRate) {
  let rms = 0;
  for (let i = 0; i < buffer.length; i += 1) {
    rms += buffer[i] * buffer[i];
  }
  rms = Math.sqrt(rms / buffer.length);
  if (rms < 0.01) {
    return null;
  }

  let r1 = 0;
  let r2 = buffer.length - 1;
  const threshold = 0.2;

  while (r1 < buffer.length / 2 && Math.abs(buffer[r1]) < threshold) {
    r1 += 1;
  }
  while (r2 > buffer.length / 2 && Math.abs(buffer[r2]) < threshold) {
    r2 -= 1;
  }

  const clipped = buffer.slice(r1, r2);
  const size = clipped.length;
  if (size < 10) {
    return null;
  }

  const corr = new Array(size).fill(0);
  for (let lag = 0; lag < size; lag += 1) {
    for (let i = 0; i + lag < size; i += 1) {
      corr[lag] += clipped[i] * clipped[i + lag];
    }
  }

  let dip = 0;
  while (dip + 1 < size && corr[dip] > corr[dip + 1]) {
    dip += 1;
  }

  let peakValue = -1;
  let peakIndex = -1;
  for (let i = dip; i < size; i += 1) {
    if (corr[i] > peakValue) {
      peakValue = corr[i];
      peakIndex = i;
    }
  }

  if (peakIndex <= 0) {
    return null;
  }

  const frequency = sampleRate / peakIndex;
  if (!Number.isFinite(frequency) || frequency < 70 || frequency > 420) {
    return null;
  }
  return frequency;
}

class VoiceCapture {
  constructor(getPhase) {
    this.getPhase = getPhase;
    this.stream = null;
    this.context = null;
    this.analyser = null;
    this.animationFrame = null;
    this.startedAt = 0;
    this.buffer = null;
    this.pitchFrameCounter = 0;

    this.totalFrames = 0;
    this.voicedFrames = 0;
    this.energySum = 0;
    this.voicedEnergySum = 0;
    this.onsets = [];
    this.pitchSamples = [];
    this.lastVoiced = false;

    this.phaseStats = {};
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.context = new AudioContext();
    const source = this.context.createMediaStreamSource(this.stream);
    this.analyser = this.context.createAnalyser();
    this.analyser.fftSize = 1024;
    this.buffer = new Float32Array(this.analyser.fftSize);
    source.connect(this.analyser);

    this.startedAt = performance.now();
    this.sampleLoop();
  }

  sampleLoop() {
    this.analyser.getFloatTimeDomainData(this.buffer);

    let sumSquares = 0;
    for (let i = 0; i < this.buffer.length; i += 1) {
      const sample = this.buffer[i];
      sumSquares += sample * sample;
    }
    const rms = Math.sqrt(sumSquares / this.buffer.length);
    const voiced = rms > 0.022;
    const elapsedSec = (performance.now() - this.startedAt) / 1000;

    this.totalFrames += 1;
    this.energySum += rms;
    if (voiced) {
      this.voicedFrames += 1;
      this.voicedEnergySum += rms;
    }

    if (voiced && !this.lastVoiced) {
      this.onsets.push(elapsedSec);
    }
    this.lastVoiced = voiced;

    const phase = this.getPhase();
    if (phase) {
      if (!this.phaseStats[phase]) {
        this.phaseStats[phase] = {
          frames: 0,
          voicedFrames: 0,
          onsets: [],
          lastVoiced: false,
        };
      }
      const stats = this.phaseStats[phase];
      stats.frames += 1;
      if (voiced) {
        stats.voicedFrames += 1;
      }
      if (voiced && !stats.lastVoiced) {
        stats.onsets.push(elapsedSec);
      }
      stats.lastVoiced = voiced;
    }

    this.pitchFrameCounter += 1;
    if (voiced && this.pitchFrameCounter % 3 === 0) {
      const pitch = autoCorrelatePitch(this.buffer, this.context.sampleRate);
      if (pitch) {
        this.pitchSamples.push(pitch);
      }
    }

    this.animationFrame = window.requestAnimationFrame(() => this.sampleLoop());
  }

  async stop() {
    if (this.animationFrame) {
      window.cancelAnimationFrame(this.animationFrame);
    }

    const durationSeconds = (performance.now() - this.startedAt) / 1000;

    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
    }
    if (this.context && this.context.state !== "closed") {
      await this.context.close();
    }

    const voiceRatioTotal = this.totalFrames > 0 ? this.voicedFrames / this.totalFrames : 0;

    let pitchStability = 0.5;
    if (this.pitchSamples.length > 1) {
      const pitchMean = mean(this.pitchSamples);
      if (pitchMean > 0) {
        const cv = std(this.pitchSamples, pitchMean) / pitchMean;
        pitchStability = clamp01(1 - (cv * 1.5));
      }
    }

    const cadenceBpm = estimateCadenceBpm(this.onsets, durationSeconds);
    const cadenceConsistency = normalizeCadenceConsistency(this.onsets);

    const voicedMeanEnergy = this.voicedFrames > 0 ? this.voicedEnergySum / this.voicedFrames : 0;
    const avgEnergy = clamp01(voicedMeanEnergy / 0.12);

    const studentStats = this.phaseStats.student;
    const guruStats = this.phaseStats.guru;

    const voiceRatioStudent = studentStats
      ? studentStats.voicedFrames / Math.max(1, studentStats.frames)
      : null;
    const voiceRatioGuru = guruStats
      ? guruStats.voicedFrames / Math.max(1, guruStats.frames)
      : null;

    return {
      duration_seconds: Number(durationSeconds.toFixed(2)),
      voice_ratio_total: Number(voiceRatioTotal.toFixed(3)),
      voice_ratio_student:
        voiceRatioStudent === null ? null : Number(clamp01(voiceRatioStudent).toFixed(3)),
      voice_ratio_guru: voiceRatioGuru === null ? null : Number(clamp01(voiceRatioGuru).toFixed(3)),
      pitch_stability: Number(clamp01(pitchStability).toFixed(3)),
      cadence_bpm: Number(Math.max(20, Math.min(220, cadenceBpm)).toFixed(2)),
      cadence_consistency: Number(clamp01(cadenceConsistency).toFixed(3)),
      avg_energy: Number(clamp01(avgEnergy).toFixed(3)),
    };
  }
}

async function playAt(seconds, muted) {
  state.mediaMuted = Boolean(muted);
  if (state.mediaMode === "fallback") {
    await playFallbackTrack(state.mediaMuted);
    return;
  }
  const started = await playYouTubeAt(seconds, state.mediaMuted);
  if (!started) {
    setMediaStatus("YouTube blocked. Fallback track engaged.");
    await switchToFallbackTrack("YouTube unavailable");
  }
}

function pauseVideo() {
  if (state.mediaMode === "fallback") {
    stopFallbackTrack();
    return;
  }
  if (!state.player) {
    return;
  }
  state.player.pauseVideo();
}

async function evaluateStage(stage, metrics) {
  const result = await api("/v1/maha-mantra/evaluate", {
    method: "POST",
    body: JSON.stringify({
      stage,
      lineage: state.lineage,
      golden_profile: GOLDEN_PROFILE,
      session_id: state.sessionId,
      metrics,
    }),
  });

  state.stageResults[stage] = result;
  renderResults();

  if (state.sessionId) {
    await api(`/v1/sessions/${state.sessionId}/events`, {
      method: "POST",
      body: JSON.stringify({
        event_type: "maha_mantra_stage_eval",
        client_event_id: `maha:${stage}:${Date.now()}`,
        payload: {
          stage,
          practice_seconds: metrics.duration_seconds,
          flow_score: result.resonance,
          pronunciation_score: result.coherence,
          cadence_bpm: metrics.cadence_bpm,
          adaptation_helpful: true,
          metrics,
          result,
        },
      }),
    });
  }

  return result;
}

async function finalizeSession() {
  if (!state.sessionId || !state.stageResults.independent) {
    return;
  }

  const overall = calculateOverall(state.stageResults);
  const endResp = await api(`/v1/sessions/${state.sessionId}/end`, {
    method: "POST",
    body: JSON.stringify({
      user_value_rating: scoreToRating(overall),
      completed_goal: state.stageResults.independent.passes_golden,
    }),
  });

  const bhav = await api(`/v1/sessions/${state.sessionId}/bhav`, {
    method: "POST",
    body: JSON.stringify({
      lineage: state.lineage,
      golden_profile: GOLDEN_PROFILE,
      persist: false,
    }),
  });

  state.finalArtifacts = {
    session_summary: endResp.summary,
    bhav,
  };
  renderResults();
}

function setButtonsDuringRun(disabled) {
  const all = [
    els.initSessionBtn,
    els.listenBtn,
    els.guidedBtn,
    els.callResponseBtn,
    els.recapBtn,
    els.independentBtn,
  ];
  all.forEach((btn) => {
    if (btn) {
      btn.disabled = disabled || btn.dataset.enabled !== "true";
    }
  });
  updateInteractionQueue();
}

function allowButton(btn) {
  btn.dataset.enabled = "true";
  if (!state.busy) {
    btn.disabled = false;
  }
  updateInteractionQueue();
}

async function runStep(stepFn) {
  if (state.busy) {
    return;
  }
  state.busy = true;
  setButtonsDuringRun(true);
  try {
    await stepFn();
  } catch (err) {
    console.error(err);
    setStageLabel("Error");
    setCountdown("- ");
    setTurn("-");
    alert(err.message || "Unexpected error");
  } finally {
    state.busy = false;
    setButtonsDuringRun(false);
    updateInteractionQueue();
  }
}

async function initSession() {
  const displayName = els.displayName.value.trim() || "Hackathon Singer";
  state.lineage = els.lineageSelect.value;

  setStageLabel("Initializing session");
  setCountdown("-");

  const user = await api("/v1/users", {
    method: "POST",
    body: JSON.stringify({ display_name: displayName }),
  });

  await api(`/v1/users/${user.id}/consent`, {
    method: "PUT",
    body: JSON.stringify({
      biometric_enabled: true,
      environmental_enabled: true,
      raw_audio_storage_enabled: false,
      policy_version: "v1",
    }),
  });

  const session = await api("/v1/sessions", {
    method: "POST",
    body: JSON.stringify({
      user_id: user.id,
      intention: "Maha Mantra learning POC session",
      mantra_key: "maha_mantra_hare_krishna_hare_rama",
      mood: "focused",
      target_duration_minutes: 3,
    }),
  });

  state.userId = user.id;
  state.sessionId = session.id;
  state.queueEventKey = null;
  state.stageResults = {};
  state.finalArtifacts = {};
  STAGE_ORDER.forEach((stageKey) => {
    const stageEl = document.getElementById(STAGE_IDS[stageKey]);
    const btn = getStageButton(stageKey);
    if (stageEl) {
      stageEl.classList.remove("active", "done");
    }
    if (btn) {
      btn.dataset.enabled = "false";
      btn.disabled = true;
    }
  });
  state.currentStage = "idle";
  syncStageCtaLabels();
  updateNavDots();
  renderResults();

  els.sessionMeta.textContent = `User ${user.id} | Session ${session.id} | Lineage ${state.lineage}`;
  els.initSessionBtn.classList.remove("primary");
  els.initSessionBtn.textContent = "Reinitialize Session";

  setStageLabel("Ready for 30-second listening");
  allowButton(els.listenBtn);
  updateInteractionQueue();
}

async function runListenStage() {
  setActiveStage("listen");
  setStageLabel("Stage 1: Listen");
  setTurn("Guru lead");
  await playAt(0, false);

  await runCountdown(30, (remaining) => {
    setCountdown(`${remaining}s`);
  });

  pauseVideo();
  markStageDone("listen");
  setTurn("-");
  setCountdown("Done");
  setStageLabel("Listen completed");

  allowButton(els.guidedBtn);
}

async function runGuidedStage() {
  setActiveStage("guided");
  setStageLabel("Stage 2: Guided follow-along");
  setTurn("Sing with track");
  setMicStatus("capturing");

  const capture = new VoiceCapture(() => "guided");
  await capture.start();
  await playAt(30, false);

  await runCountdown(45, (remaining) => {
    setCountdown(`${remaining}s`);
  });

  pauseVideo();
  const metrics = await capture.stop();
  setMicStatus("stopped");

  await evaluateStage("guided", metrics);

  markStageDone("guided");
  setStageLabel("Guided stage scored");
  setTurn("-");
  setCountdown("Done");

  allowButton(els.callResponseBtn);
}

async function callTurn({ label, phase, muted, round, totalRounds, seconds }) {
  state.callPhase = phase;
  setTurn(`${label} ${round}/${totalRounds}`);
  setMediaMuted(muted);

  await runCountdown(seconds, (remaining) => {
    setCountdown(`${label} ${remaining}s`);
  });
}

async function runCallResponseStage() {
  setActiveStage("call_response");
  setStageLabel("Stage 3: Call-response");
  setMicStatus("capturing");

  const capture = new VoiceCapture(() => state.callPhase);
  await capture.start();
  await playAt(76, false);

  const rounds = 4;
  const turnSeconds = 5;

  for (let round = 1; round <= rounds; round += 1) {
    await callTurn({
      label: "Guru",
      phase: "guru",
      muted: false,
      round,
      totalRounds: rounds,
      seconds: turnSeconds,
    });
    await callTurn({
      label: "Student",
      phase: "student",
      muted: true,
      round,
      totalRounds: rounds,
      seconds: turnSeconds,
    });
  }

  pauseVideo();
  setMediaMuted(false);
  const metrics = await capture.stop();
  setMicStatus("stopped");

  await evaluateStage("call_response", metrics);

  markStageDone("call_response");
  setStageLabel("Call-response scored");
  setTurn("-");
  setCountdown("Done");

  allowButton(els.recapBtn);
}

async function showRecap() {
  setActiveStage("recap");
  setStageLabel("Stage 4: Performance recap");
  setTurn("Review");
  setCountdown("- ");
  renderResults();

  await wait(400);
  markStageDone("recap");
  allowButton(els.independentBtn);
}

async function runIndependentStage() {
  setActiveStage("independent");
  setStageLabel("Stage 5: Independent performance");
  setTurn("Solo chanting");
  setMicStatus("capturing");

  const capture = new VoiceCapture(() => "independent");
  await capture.start();

  setMediaMuted(true);

  await runCountdown(30, (remaining) => {
    setCountdown(`${remaining}s`);
  });

  const metrics = await capture.stop();
  setMicStatus("stopped");

  await evaluateStage("independent", metrics);
  await finalizeSession();

  markStageDone("independent");
  setStageLabel("Independent stage complete");
  setTurn("Finished");
  setCountdown("Done");
  setMediaMuted(false);
}

/* ===== Animation Utilities ===== */

function animateCounter(el, target, duration, decimals) {
  const start = performance.now();
  const dp = decimals || 3;
  function tick(now) {
    const elapsed = now - start;
    const t = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = (target * eased).toFixed(dp);
    if (t < 1) {
      requestAnimationFrame(tick);
    }
  }
  requestAnimationFrame(tick);
}

function animateBar(el, targetPercent, delay) {
  setTimeout(() => {
    el.style.width = `${targetPercent}%`;
  }, delay || 0);
}

function updateNavDots() {
  const dots = document.querySelectorAll(".nav-dot");
  dots.forEach((dot, i) => {
    const key = STAGE_ORDER[i];
    const stageEl = document.getElementById(STAGE_IDS[key]);
    dot.classList.remove("active", "done");
    if (stageEl && stageEl.classList.contains("done")) {
      dot.classList.add("done");
    } else if (stageEl && stageEl.classList.contains("active")) {
      dot.classList.add("active");
    }
  });

  const journeyNodes = document.querySelectorAll(".journey-node");
  journeyNodes.forEach((node) => {
    const key = node.dataset.stage;
    const stageEl = key ? document.getElementById(STAGE_IDS[key]) : null;
    node.classList.remove("active", "done");
    if (stageEl && stageEl.classList.contains("done")) {
      node.classList.add("done");
    } else if (stageEl && stageEl.classList.contains("active")) {
      node.classList.add("active");
    }
  });
}

function syntaxHighlightJson(json) {
  return json.replace(
    /("(?:\\.|[^"\\])*")\s*:/g,
    '<span class="json-key">$1</span>:'
  ).replace(
    /:\s*("(?:\\.|[^"\\])*")/g,
    ': <span class="json-string">$1</span>'
  ).replace(
    /:\s*(\d+\.?\d*)/g,
    ': <span class="json-number">$1</span>'
  ).replace(
    /:\s*(true|false)/g,
    ': <span class="json-bool">$1</span>'
  ).replace(
    /:\s*(null)/g,
    ': <span class="json-null">$1</span>'
  );
}

function initWordReveal() {
  const h1 = document.querySelector("h1.word-reveal");
  if (!h1) return;
  const html = h1.innerHTML;
  let wordIndex = 0;
  const wrapped = html.replace(/(<em>.*?<\/em>|\S+)/g, (match) => {
    const delay = 200 + wordIndex * 80;
    wordIndex++;
    if (match.startsWith("<em>")) {
      return `<span class="word" style="animation-delay:${delay}ms">${match}</span>`;
    }
    return `<span class="word" style="animation-delay:${delay}ms">${match}</span>`;
  });
  h1.innerHTML = wrapped;
}

function initRevealAnimations() {
  const targets = document.querySelectorAll(".reveal-up");
  if (!targets.length) return;
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
          setTimeout(() => {
            entry.target.classList.add("revealed");
          }, i * 100);
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
  );
  targets.forEach((el) => observer.observe(el));
}

function bindEvents() {
  els.initSessionBtn.dataset.enabled = "true";

  els.initSessionBtn.addEventListener("click", () => runStep(initSession));
  els.listenBtn.addEventListener("click", () => runStep(runListenStage));
  els.guidedBtn.addEventListener("click", () => runStep(runGuidedStage));
  els.callResponseBtn.addEventListener("click", () => runStep(runCallResponseStage));
  els.recapBtn.addEventListener("click", () => runStep(showRecap));
  els.independentBtn.addEventListener("click", () => runStep(runIndependentStage));
  els.queuePrimaryBtn.addEventListener("click", () => {
    const action = els.queuePrimaryBtn.dataset.action;
    if (!action) {
      return;
    }
    if (action === "init") {
      if (!els.initSessionBtn.disabled) {
        els.initSessionBtn.click();
      }
      return;
    }
    const btn = getStageButton(action);
    if (btn && !btn.disabled) {
      btn.click();
    }
  });
  els.useFallbackBtn.addEventListener("click", () => {
    switchToFallbackTrack("manual selection").catch((err) => {
      console.warn("manual fallback failed", err);
    });
  });
  els.retryYoutubeBtn.addEventListener("click", () => {
    setMediaMode("youtube");
    stopFallbackTrack();
    setMediaStatus("Media mode: YouTube (retry armed for next playback)");
  });
}

function setInitialUiState() {
  setStageLabel("Idle");
  setTurn("-");
  setCountdown("-");
  setMicStatus("idle");
  setMediaMode("youtube");
  setMediaStatus("Media mode: YouTube");

  [els.listenBtn, els.guidedBtn, els.callResponseBtn, els.recapBtn, els.independentBtn].forEach((btn) => {
    btn.dataset.enabled = "false";
    btn.disabled = true;
  });

  syncStageCtaLabels();
  updateInteractionQueue();
  renderResults();
}

bindEvents();
setInitialUiState();
initWordReveal();
initRevealAnimations();
