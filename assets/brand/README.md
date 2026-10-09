# Porchlight logomark concept

Current applied artwork is the owner's root-level `Porchlight-logomark-transparent.png` for the interface and `Porchlight-logomark-202B27-background.png` for app icons/favicons. Both are 800×800 source masters and remain intact. Previous generated concepts below are retained as design history.

Run `.venv/Scripts/python.exe scripts/generate-app-icons.py` from the repository root to recreate the versioned exports under `apps/web/public/`. It uses the existing configured FFmpeg, Lanczos resizing, maximum lossless PNG compression and stripped ancillary metadata; no additional package is required. The transparent mark is 256×256 for existing 48/64 CSS-pixel logo placements, including high-density displays. Opaque icons are 16/32/48 (favicon), 180 (Apple touch), 192/512 (PWA), plus a padded 512 maskable icon whose artwork fits Android's central safe circle. The multi-image ICO contains 16/32/48 PNG entries. App launch colours match `#202B27`; notification icons use the same new app artwork. Versioned URLs avoid old favicon reuse. Existing installed launchers may need a reinstall to pick up their icon.

`porchlight-logomark-concept-v1.png` is a transparent raster concept combining a P-shaped doorway with a hanging porch lamp and its warm beam of light.

Palette direction: existing forest green `#283F35` and amber `#EAB951`. The generated raster has subtle tonal variation; these codes are the intended solid colors for a future vector master.

This is a branding proposal, not yet wired into the application. A vector master and small-size, dark-background, monochrome, and app-icon variants remain to be prepared once the direction is selected. Dark-background usage needs a lighter doorway color for contrast.

Created using the built-in image-generation tool, with one simplification pass. No private footage was used.

## Final refinement prompt

Use case: logo-brand. Refine this Porchlight logomark into a much cleaner flat geometric identity. Preserve its core idea: a bold forest-green capital P whose interior is a welcoming doorway with an amber porch lamp. Preserve transparent background and centered square layout with generous margins. Make ONLY a simplified flat design version: exact solid fills #283F35 green and #EAB951 amber, no gradients or texture or glow. Remove the two separate steps at the bottom entirely; give the P a simple clean flat foot. Replace the complex lamp cap and curved door-like light shape with ONE amber circular lamp and ONE simple tapered triangular beam opening downward toward the doorway floor, separated by a small clean gap. Keep broad rounded architecture and balanced negative space. The entire mark must use just a few bold geometric shapes and read clearly at 24 pixels. No words, no text, no roof, no camera, no eye, no shield. Very crisp smooth edges and completely transparent background.
