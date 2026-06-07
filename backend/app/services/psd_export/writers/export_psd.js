const fs = require('fs');
require('ag-psd/initialize-canvas');
const { writePsdBuffer } = require('ag-psd');

function readRawRgba(imagePath, width, height) {
  if (!imagePath || !width || !height) return null;
  const raw = fs.readFileSync(imagePath);
  const expected = width * height * 4;
  if (raw.length !== expected) {
    throw new Error(`Invalid RGBA length for ${imagePath}: got ${raw.length}, expected ${expected}`);
  }
  return {
    width,
    height,
    data: new Uint8ClampedArray(raw.buffer, raw.byteOffset, raw.byteLength),
  };
}

function parseColor(color) {
  let r = 0, g = 0, b = 0;
  if (color && color.startsWith('#')) {
    let hex = color.substring(1);
    if (hex.length === 3) {
      hex = hex.split('').map(c => c + c).join('');
    }
    if (hex.length === 6 || hex.length === 8) {
      r = parseInt(hex.substring(0, 2), 16);
      g = parseInt(hex.substring(2, 4), 16);
      b = parseInt(hex.substring(4, 6), 16);
    }
  }
  return { r, g, b, a: 255 };
}

function parseFontName(font, fontWeight) {
  const fallback = fontWeight === 'bold' ? 'Arial-BoldMT' : 'ArialMT';
  if (!font) return fallback;
  const match = font.match(/"([^"]+)"|'([^']+)'|([^,]+)/);
  const name = match ? (match[1] || match[2] || match[3]).trim() : fallback;
  if (!name) return fallback;
  if (fontWeight === 'bold' && /^arial$/i.test(name)) return 'Arial-BoldMT';
  if (/^arial$/i.test(name)) return 'ArialMT';
  return name;
}

function groupDisplayName(path) {
  const name = String(path || '').split('/').filter(Boolean).pop() || 'Layers';
  return name.replace(/^\d+_/, '');
}

function compareByGroupOrder(a, b, orderIndex) {
  const ai = orderIndex.has(a.groupPath || '') ? orderIndex.get(a.groupPath || '') : -1;
  const bi = orderIndex.has(b.groupPath || '') ? orderIndex.get(b.groupPath || '') : -1;
  if (ai !== bi) return bi - ai;
  return String(a.name || '').localeCompare(String(b.name || ''));
}

function buildGroupedChildren(entries, groupOrder) {
  const root = { children: [], childGroups: new Map(), groupPath: '' };
  const groupByPath = new Map([['', root]]);
  const orderIndex = new Map((groupOrder || []).map((path, index) => [path, index]));

  function ensureGroup(groupPath) {
    if (!groupPath) return root;
    if (groupByPath.has(groupPath)) return groupByPath.get(groupPath);

    const parts = groupPath.split('/').filter(Boolean);
    let currentPath = '';
    let parent = root;
    for (const part of parts) {
      currentPath = currentPath ? `${currentPath}/${part}` : part;
      let group = groupByPath.get(currentPath);
      if (!group) {
        group = {
          name: groupDisplayName(part),
          opened: true,
          children: [],
          childGroups: new Map(),
          groupPath: currentPath,
        };
        parent.childGroups.set(currentPath, group);
        groupByPath.set(currentPath, group);
      }
      parent = group;
    }
    return parent;
  }

  for (const entry of entries) {
    const parent = ensureGroup(entry.groupPath || '');
    parent.children.push(entry.layer);
  }

  function finalize(group) {
    const groups = [...group.childGroups.values()]
      .sort((a, b) => compareByGroupOrder(a, b, orderIndex))
      .map(finalize);
    const layers = group.children.sort((a, b) => {
      const az = typeof a.zIndex === 'number' ? a.zIndex : -1;
      const bz = typeof b.zIndex === 'number' ? b.zIndex : -1;
      if (az !== bz) return bz - az;
      return String(a.name || '').localeCompare(String(b.name || ''));
    });
    const children = [...groups, ...layers].map(child => {
      if (!child.children) {
        const { zIndex, ...cleanLayer } = child;
        return cleanLayer;
      }
      return child;
    });
    if (group === root) return children;
    return {
      name: group.name,
      opened: true,
      children,
    };
  }

  return finalize(root);
}

async function main() {
  const manifestPath = process.argv[2];
  const outputPath = process.argv[3];

  if (!manifestPath || !outputPath) {
    console.error('Usage: node export_psd.js <manifest.json> <output.psd>');
    process.exit(1);
  }

  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const width = Number(manifest.width);
  const height = Number(manifest.height);
  if (!width || !height || isNaN(width) || isNaN(height)) {
    throw new Error('PSD manifest is missing a valid canvas width/height');
  }

  const entries = [];

  for (const t of (manifest.textLayers || [])) {
    const left = Math.round(t.x);
    const top = Math.round(t.y);
    const right = Math.round(t.x + t.w);
    const bottom = Math.round(t.y + t.h);
    const fontSize = t.fontSize || 24;
    const layer = {
      name: (t.text || 'Text').substring(0, 30),
      type: 'text',
      hidden: t.visible === false,
      left,
      top,
      right,
      bottom,
      zIndex: typeof t.zIndex === 'number' ? t.zIndex : 100000,
      text: {
        text: t.text || '',
        transform: [1, 0, 0, 1, left, top],
        antiAlias: 'smooth',
        orientation: 'horizontal',
        shapeType: 'box',
        boxBounds: [0, 0, Math.max(1, bottom - top), Math.max(1, right - left)],
        style: {
          font: { name: parseFontName(t.font, t.fontWeight) },
          fontSize,
          fauxBold: t.fontWeight === 'bold',
          fillColor: parseColor(t.color),
          leading: Math.ceil(fontSize * 1.2),
        },
        paragraphStyle: {
          justification: t.textAlign === 'center' ? 'center' : (t.textAlign === 'right' ? 'right' : 'left'),
        },
      },
    };
    const imageData = readRawRgba(t.imagePath, t.imageW, t.imageH);
    if (imageData) {
      layer.imageData = imageData;
      layer.right = layer.left + imageData.width;
      layer.bottom = layer.top + imageData.height;
    }
    entries.push({ groupPath: t.groupPath || '20_Text', layer });
  }

  for (const r of (manifest.rasterLayers || [])) {
    const imageW = Number(r.imageW || width);
    const imageH = Number(r.imageH || height);
    const imageData = readRawRgba(r.imagePath, imageW, imageH);
    if (!imageData) continue;
    const left = Math.round(r.x || 0);
    const top = Math.round(r.y || 0);
    entries.push({
      groupPath: r.groupPath || '',
      layer: {
        name: r.name || 'Raster Layer',
        hidden: r.visible === false,
        opacity: typeof r.opacity === 'number' ? r.opacity : 1,
        left,
        top,
        right: left + imageData.width,
        bottom: top + imageData.height,
        zIndex: typeof r.zIndex === 'number' ? r.zIndex : 0,
        imageData,
      },
    });
  }

  const children = buildGroupedChildren(entries, manifest.groupOrder || []);
  const psd = { width, height, children };
  const buffer = writePsdBuffer(psd, { generateThumbnail: false, trim: false });
  if (!buffer) {
    throw new Error('writePsdBuffer returned undefined or null');
  }
  fs.writeFileSync(outputPath, buffer);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
