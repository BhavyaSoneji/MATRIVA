import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
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
          fontSize: 20,
        }}
      >
        M
      </div>
    ),
    { ...size }
  );
}
