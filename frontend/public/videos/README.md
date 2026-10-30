# MediSmart Authentication Background Video Assets

This directory hosts the video assets for the MediSmart authentication screens (`/login` and `/register`).

## Target Asset File Paths

Place the background video file at:
* **Primary (MP4)**: `frontend/public/videos/auth-healthcare-bg.mp4`
* **Optional WebM**: `frontend/public/videos/auth-healthcare-bg.webm`

When present, the video is automatically discovered and played in the background with `autoplay`, `muted`, `loop`, and `playsInline`.

---

## Recommended Video Specifications

To ensure optimal performance, low latency, and smooth looping on all devices:

| Parameter | Specification | Recommendation |
| :--- | :--- | :--- |
| **Container & Codec** | MP4 (`H.264 / AVC`) | Universally supported across mobile and desktop browsers |
| **Resolution** | 1080p (`1920x1080`) or 720p (`1280x720`) | 720p/1080p web-optimized |
| **Aspect Ratio** | 16:9 (`object-fit: cover`) | Covers all viewport shapes gracefully |
| **Bitrate** | 1.5 – 2.5 Mbps | Keeps total file size between 2 MB – 5 MB |
| **Framerate** | 24 – 30 fps | Smooth cinematic playback |
| **Duration** | 8 – 20 seconds | Ideal for continuous, seamless ambient loop |
| **Audio** | None / Stripped | Background video is permanently muted for accessibility |

---

## Approved Licensing-Safe Stock Video Sources

For production deployments, select royalty-free, commercial-safe healthcare footage from these repositories:

1. **Pexels Videos (Pexels License)**
   - *License*: Free for commercial and personal use. No attribution required. Modifications permitted.
   - *Search Terms*: `"modern hospital corridor"`, `"doctor consulting patient"`, `"healthcare team"`, `"medical clinic lobby"`
   - *URL*: [Pexels Medical & Hospital Stock Videos](https://www.pexels.com/search/videos/medical%20hospital/)

2. **Pixabay Videos (Pixabay License)**
   - *License*: Free for commercial use. No attribution required.
   - *Search Terms*: `"hospital hallway"`, `"doctor patient consultation"`, `"clinic interior"`
   - *URL*: [Pixabay Hospital Stock Footage](https://pixabay.com/videos/search/hospital/)

3. **Mixkit (Mixkit Free Stock Video License)**
   - *License*: Free for commercial and non-commercial projects.
   - *Search Terms*: `"healthcare"`, `"hospital"`, `"doctor"`
   - *URL*: [Mixkit Healthcare Stock Videos](https://mixkit.co/free-stock-video/hospital/)

---

## Content & Aesthetic Guidelines

* **Appropriate**: Calm, tranquil hospital corridors, doctors conversing warmly with patients, nurses checking digital charts, bright modern medical architecture, soft natural and ambient illumination.
* **Prohibited**: Invasive procedures, surgeries, graphic medical scenes, distress, rapid camera pans, flashing lights, or jarring zoom transitions.

---

## Fallback & Accessibility Mechanisms

* **Poster Fallback**: If the video is loading, unavailable, or unsupported on the user's connection, `frontend/public/images/auth-poster.jpg` renders immediately with zero layout shift.
* **Reduced Motion**: If the user's OS or browser has `prefers-reduced-motion: reduce` enabled, video rendering and autoplay are automatically suppressed in favor of the static high-resolution poster and ambient gradient.
* **Screen Readers**: The video element is marked with `aria-hidden="true"` and `tabIndex={-1}` so assistive technologies ignore the purely decorative background.
