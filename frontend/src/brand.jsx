import React from 'react';

/* The maker's name and link, used wherever "Elevatics AI" appears so it is always a link to the company site. */
export const MAKER_NAME = 'Elevatics AI';
export const MAKER_URL = 'https://www.elevatics.ai/';

export function Maker({ children = MAKER_NAME }) {
  return (
    <a
      className="maker-link"
      href={MAKER_URL}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  );
}
