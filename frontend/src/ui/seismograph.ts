import type { Store } from '../store';
import { byId, prefersReducedMotion } from './dom';

type Levels = () => { tutor: number; student: number };

const STEP_PX = 3;
const SMOOTHING = 0.35;

/**
 * Draws both voices as a scrolling seismogram: Terra above the baseline, the
 * student below it. It freezes while paused, like the lesson.
 */
export function mountSeismograph(store: Store, levels: Levels): void {
    const canvas = byId<HTMLCanvasElement>('seismo');
    const context = canvas.getContext('2d')!;
    let tutor: number[] = [];
    let student: number[] = [];
    let smoothTutor = 0;
    let smoothStudent = 0;
    let direction: 1 | -1 = 1;
    let colors = readColors(canvas);
    let frame = 0;

    const resize = () => {
        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.round(canvas.clientWidth * ratio);
        canvas.height = Math.round(canvas.clientHeight * ratio);
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        colors = readColors(canvas);
    };
    new ResizeObserver(resize).observe(canvas);
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', resize);

    const tick = () => {
        frame = requestAnimationFrame(tick);
        const state = store.get();
        if (state.paused) return;

        const now = levels();
        smoothTutor += (now.tutor - smoothTutor) * SMOOTHING;
        smoothStudent += (now.student - smoothStudent) * SMOOTHING;
        const capacity = Math.ceil(canvas.clientWidth / STEP_PX) + 1;
        // A full trace keeps its length, so the swing needs its own counter.
        direction = direction === 1 ? -1 : 1;
        tutor = pushSample(tutor, smoothTutor, capacity, direction);
        student = pushSample(student, smoothStudent, capacity, direction);
        draw(context, canvas, colors, tutor, student);
    };

    store.subscribe((state, previous) => {
        const live = state.phase === 'live';
        if (live && previous.phase !== 'live') {
            tutor = [];
            student = [];
            resize();
            frame = requestAnimationFrame(tick);
        } else if (!live && frame) {
            cancelAnimationFrame(frame);
            frame = 0;
        }
    });
}

/** A seismogram swings both ways; alternate the sign and add some jitter. */
function pushSample(
    trace: number[],
    level: number,
    capacity: number,
    direction: 1 | -1
): number[] {
    const jitter = 0.55 + Math.random() * 0.45;
    const floor = 0.015 * (Math.random() - 0.5);
    const next = [...trace, direction * level * jitter + floor];
    return next.length > capacity ? next.slice(next.length - capacity) : next;
}

interface Colors {
    tutor: string;
    student: string;
    grid: string;
}

function readColors(canvas: HTMLCanvasElement): Colors {
    const style = getComputedStyle(canvas);
    return {
        tutor: style.getPropertyValue('--moss').trim() || '#2f7a57',
        student: style.getPropertyValue('--signal').trim() || '#f0a33a',
        grid: style.getPropertyValue('--contour').trim() || '#b7c6ce',
    };
}

function draw(
    context: CanvasRenderingContext2D,
    canvas: HTMLCanvasElement,
    colors: Colors,
    tutor: number[],
    student: number[]
): void {
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    context.clearRect(0, 0, width, height);

    // Faint time ticks, like chart paper.
    context.strokeStyle = colors.grid;
    context.globalAlpha = 0.5;
    context.lineWidth = 1;
    context.beginPath();
    for (let x = width % 48; x < width; x += 48) {
        context.moveTo(x + 0.5, height * 0.2);
        context.lineTo(x + 0.5, height * 0.8);
    }
    context.stroke();
    context.globalAlpha = 1;

    const reduced = prefersReducedMotion();
    trace(context, reduced ? tutor.slice(-1) : tutor, width, height * 0.3, height * 0.28, colors.tutor, reduced);
    trace(context, reduced ? student.slice(-1) : student, width, height * 0.72, height * 0.24, colors.student, reduced);
}

function trace(
    context: CanvasRenderingContext2D,
    samples: number[],
    width: number,
    baseline: number,
    amplitude: number,
    color: string,
    asBar: boolean
): void {
    context.strokeStyle = color;
    context.fillStyle = color;
    if (asBar) {
        // Reduced motion: a still bar whose length follows the voice.
        const level = Math.abs(samples[0] ?? 0);
        context.fillRect(0, baseline - 3, Math.max(6, level * width), 6);
        return;
    }
    context.lineWidth = 1.75;
    context.lineJoin = 'round';
    context.beginPath();
    const pen = width - 4;
    const start = pen - (samples.length - 1) * STEP_PX;
    samples.forEach((sample, i) => {
        const x = start + i * STEP_PX;
        const y = baseline - sample * amplitude;
        if (i === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
    });
    context.stroke();
    // The pen, where the newest sample is drawn.
    const last = samples.at(-1) ?? 0;
    context.beginPath();
    context.arc(pen, baseline - last * amplitude, 3.5, 0, Math.PI * 2);
    context.fill();
}
