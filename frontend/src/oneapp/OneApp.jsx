// OneApp mobile view. Owned by P4.
// Not a native app - a phone-shaped web frame that reuses the SAME components and
// the SAME session_id as OneShop. That shared session is what proves omnichannel.
import React from "react";

export default function OneApp({ children }) {
  return (
    <div className="phone-frame">
      <div className="container">{children}</div>
    </div>
  );
}
