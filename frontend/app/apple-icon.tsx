import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#1C241C",
          color: "#F5F2EA",
          fontFamily: "Georgia, serif",
          fontSize: 108,
        }}
      >
        M
      </div>
    ),
    { ...size }
  );
}
