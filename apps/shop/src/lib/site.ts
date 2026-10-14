/** The shop's LINE Official Account basic ID. Same value as LINE_OA_ID on the API; set NEXT_PUBLIC_LINE_OA_ID to change it. */
export const LINE_OA_ID = process.env.NEXT_PUBLIC_LINE_OA_ID || "@maehai";

/** Opens the "add friend" screen for the shop's LINE account. */
export const LINE_ADD_URL = `https://line.me/R/ti/p/${encodeURIComponent(LINE_OA_ID)}`;
