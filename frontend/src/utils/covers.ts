export const EXTENSION_REGEX = /\.png|\.jpg|\.jpeg$/;

function hashString(str: string) {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 100);
  }
  return Math.abs(h);
}

function translatedBGs(str: string) {
  return {
    left: {
      x: -150 + (hashString(str) % 100),
      y: -75 + (hashString(str) % 50),
    },
    right: {
      x: 350 - (hashString(str) % 100),
      y: 250 - (hashString(str) % 50),
    },
  };
}

function bgRotation(str: string): number {
  return hashString(str) % 60;
}

function strToObjUrl(str: string) {
  const blob = new Blob([str], { type: "image/svg+xml" });
  return URL.createObjectURL(blob);
}

export function getCollectionCoverImage(name: string): string {
  const tbgs = translatedBGs(name);
  const bgr = bgRotation(name);

  const svgString = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800"><g fill="none" mask="url(#a)"><path fill="#553E98" d="M0 0h600v800H0z"/><path fill="#371f69" d="M0 580c120 10 180-130 270-190s220-70 290-150c80-90 140-210 120-320S520-250 420-310C340 30 250 0 160-20S-10-50-90-20s-150 70-200 140-60 150-85 230c-30 100-130 200-90 290s190 70 270 130c45-340 85-200 195-190" style="transform-origin:center;transform:translate(${tbgs.left.x}px,${tbgs.left.y}px) rotate(${bgr}deg);"/><path fill="#FF9B85" d="M600 1060c100 30 230 40 310-40s30-210 70-310c35-90 130-150 140-240 10-100-10-220-90-290s-200-40-300-60c-90-20-180-60-270-30S310 200 240 260C170 330 50 380 40 480s110 160 170 240c50 70 90 130 150 180 70 60 140 140 230 160" style="transform-origin:center;transform:translate(${tbgs.right.x}px,${tbgs.right.y}px) rotate(${bgr}deg);"/><path d="M201.212 336.962h-26.135v182.942c0 14.374 11.76 26.134 26.135 26.134h182.942v-26.134H201.212zm209.076-52.27H253.481c-14.374 0-26.135 11.76-26.135 26.135v156.808c0 14.374 11.76 26.134 26.135 26.134h156.807c14.375 0 26.135-11.76 26.135-26.134V310.827c0-14.374-11.76-26.135-26.135-26.135m0 130.673-32.668-19.6-32.668 19.6V310.827h65.336z" style="fill:#f9f9f9;stroke-width:13.0673"/></g><defs><mask id="a"><path fill="#fff" d="M0 0h600v800H0z"/></mask></defs></svg>`;

  return strToObjUrl(svgString);
}

export function getFavoriteCoverImage(name: string): string {
  const tbgs = translatedBGs(name);
  const bgr = bgRotation(name);

  const svgString = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800"><g fill="none" mask="url(#a)"><path fill="#553E98" d="M0 0h600v800H0z"/><path fill="#371f69" d="M0 580c120 10 180-130 270-190s220-70 290-150c80-90 140-210 120-320S520-250 420-310C340 30 250 0 160-20S-10-50-90-20s-150 70-200 140-60 150-85 230c-30 100-130 200-90 290s190 70 270 130c45-340 85-200 195-190" style="transform-origin:center;transform:translate(${tbgs.left.x}px,${tbgs.left.y}px) rotate(${bgr}deg);"/><path fill="#FF9B85" d="M600 1060c100 30 230 40 310-40s30-210 70-310c35-90 130-150 140-240 10-100-10-220-90-290s-200-40-300-60c-90-20-180-60-270-30S310 200 240 260C170 330 50 380 40 480s110 160 170 240c50 70 90 130 150 180 70 60 140 140 230 160" style="transform-origin:center;transform:translate(${tbgs.right.x}px,${tbgs.right.y}px) rotate(${bgr}deg);"/><path d="M300 479.05 392.7 535l-24.6-105.45L450 358.6l-107.85-9.3L300 250l-42.15 99.3L150 358.6l81.75 70.95L207.3 535Z" style="fill:#f9f9f9;stroke-width:225"/></g><defs><mask id="a"><path fill="#fff" d="M0 0h600v800H0z"/></mask></defs></svg>`;

  return strToObjUrl(svgString);
}

export function getMissingCoverImage(name: string): string {
  const tbgs = translatedBGs(name);
  const bgr = bgRotation(name);
  const icoR = [90, 0, 270, 180][hashString(name) % 4];

  const svgString = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800"><g fill="none" mask="url(#a)"><path fill="#553E98" d="M0 0h600v800H0z"/><path fill="#371f69" d="M0 580c120 10 180-130 270-190s220-70 290-150c80-90 140-210 120-320S520-250 420-310C340 30 250 0 160-20S-10-50-90-20s-150 70-200 140-60 150-85 230c-30 100-130 200-90 290s190 70 270 130c45-340 85-200 195-190" style="transform-origin:center;transform:translate(${tbgs.left.x}px,${tbgs.left.y}px) rotate(${bgr}deg);"/><path fill="#FF9B85" d="M600 1060c100 30 230 40 310-40s30-210 70-310c35-90 130-150 140-240 10-100-10-220-90-290s-200-40-300-60c-90-20-180-60-270-30S310 200 240 260C170 330 50 380 40 480s110 160 170 240c50 70 90 130 150 180 70 60 140 140 230 160" style="transform-origin:center;transform:translate(${tbgs.right.x}px,${tbgs.right.y}px) rotate(${bgr}deg);"/><path d="M204.545 345.455A54.545 54.545 0 0 1 259.091 400a54.545 54.545 0 0 1-54.546 54.545A54.545 54.545 0 0 1 150 400a54.545 54.545 0 0 1 54.545-54.545M300 250a54.545 54.545 0 0 1 54.545 54.545A54.545 54.545 0 0 1 300 359.091a54.545 54.545 0 0 1-54.545-54.546A54.545 54.545 0 0 1 300 250m0 190.91a54.545 54.545 0 0 1 54.545 54.545A54.545 54.545 0 0 1 300 550a54.545 54.545 0 0 1-54.545-54.545A54.545 54.545 0 0 1 300 440.909m95.455-95.454A54.545 54.545 0 0 1 450 400a54.545 54.545 0 0 1-54.545 54.545A54.545 54.545 0 0 1 340.909 400a54.545 54.545 0 0 1 54.546-54.545m-190.91 27.272A27.273 27.273 0 0 0 177.273 400a27.273 27.273 0 0 0 27.272 27.273A27.273 27.273 0 0 0 231.818 400a27.273 27.273 0 0 0-27.273-27.273m190.91 0A27.273 27.273 0 0 0 368.182 400a27.273 27.273 0 0 0 27.273 27.273A27.273 27.273 0 0 0 422.727 400a27.273 27.273 0 0 0-27.272-27.273M300 468.182a27.273 27.273 0 0 0-27.273 27.273A27.273 27.273 0 0 0 300 522.727a27.273 27.273 0 0 0 27.273-27.272A27.273 27.273 0 0 0 300 468.182" style="fill:#f9f9f9;stroke-width:13.6364;transform-origin:center;transform:rotate(${icoR}deg);"/></g><defs><mask id="a"><path fill="#fff" d="M0 0h600v800H0z"/></mask></defs></svg>`;

  return strToObjUrl(svgString);
}

export function getUnmatchedCoverImage(name: string): string {
  const tbgs = translatedBGs(name);
  const bgr = bgRotation(name);

  const svgString = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800"><g fill="none" mask="url(#a)"><path fill="#553E98" d="M0 0h600v800H0z"/><path fill="#371f69" d="M0 580c120 10 180-130 270-190s220-70 290-150c80-90 140-210 120-320S520-250 420-310C340 30 250 0 160-20S-10-50-90-20s-150 70-200 140-60 150-85 230c-30 100-130 200-90 290s190 70 270 130c45-340 85-200 195-190" style="transform-origin:center;transform:translate(${tbgs.left.x}px,${tbgs.left.y}px) rotate(${bgr}deg);"/><path fill="#FF9B85" d="M600 1060c100 30 230 40 310-40s30-210 70-310c35-90 130-150 140-240 10-100-10-220-90-290s-200-40-300-60c-90-20-180-60-270-30S310 200 240 260C170 330 50 380 40 480s110 160 170 240c50 70 90 130 150 180 70 60 140 140 230 160" style="transform-origin:center;transform:translate(${tbgs.right.x}px,${tbgs.right.y}px) rotate(${bgr}deg);"/><path d="M300 225c-8.748 0-17.496 3.324-24.669 10.322L135.366 375.287a34.536 34.536 0 0 0 0 49.338L275.331 564.59a34.536 34.536 0 0 0 49.338 0l139.965-139.965a34.536 34.536 0 0 0 0-49.338L324.669 235.322C317.496 228.324 308.748 225 300 225m0 86.603c47.238 1.925 67.708 49.513 39.89 85.03-7.348 8.747-19.07 14.52-25.019 22.044-6.123 7.523-6.123 16.27-6.123 25.018h-26.244c0-14.871 0-27.293 6.124-36.04 5.773-8.748 17.495-13.997 24.844-19.77 21.52-19.77 15.92-47.589-13.472-49.863-14.346 0-26.243 11.722-26.243 26.418h-26.244c0-29.218 23.62-52.837 52.487-52.837m-17.496 149.588h26.244v26.243h-26.244z" style="fill:#f9f9f9;stroke-width:17.4956"/></g><defs><mask id="a"><path fill="#fff" d="M0 0h600v800H0z"/></mask></defs></svg>`;

  return strToObjUrl(svgString);
}

export function getEmptyCoverImage(name: string): string {
  const tbgs = translatedBGs(name);
  const bgr = bgRotation(name);

  const svgString = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800"><g fill="none" mask="url(#a)"><path fill="#553E98" d="M0 0h600v800H0z"/><path fill="#371f69" d="M0 580c120 10 180-130 270-190s220-70 290-150c80-90 140-210 120-320S520-250 420-310C340 30 250 0 160-20S-10-50-90-20s-150 70-200 140-60 150-85 230c-30 100-130 200-90 290s190 70 270 130c45-340 85-200 195-190" style="transform-origin:center;transform:translate(${tbgs.left.x}px,${tbgs.left.y}px) rotate(${bgr}deg);"/><path fill="#FF9B85" d="M600 1060c100 30 230 40 310-40s30-210 70-310c35-90 130-150 140-240 10-100-10-220-90-290s-200-40-300-60c-90-20-180-60-270-30S310 200 240 260C170 330 50 380 40 480s110 160 170 240c50 70 90 130 150 180 70 60 140 140 230 160" style="transform-origin:center;transform:translate(${tbgs.right.x}px,${tbgs.right.y}px) rotate(${bgr}deg);"/></g><defs><mask id="a"><path fill="#fff" d="M0 0h600v800H0z"/></mask></defs></svg>`;

  return strToObjUrl(svgString);
}
