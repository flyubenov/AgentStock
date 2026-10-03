/** The Share button's link and text (ticker links spec §6). Always the canonical
 *  site, whatever host the page is on, and tagged so whoever opens it is recorded
 *  as channel `share` (B1). */
export const shareUrl = (t: string) => `https://intrinsica.io/t/${t}?ref=share`
export const shareText = (t: string) => `${t} on Intrinsica: quality business? Durable moat? Fair price?`
