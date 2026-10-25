export const SOURCE_INTAKE_OPTIONS = [
  { id: "ldxp", label: "链动小铺" },
  { id: "16688", label: "16688" },
  { id: "independent", label: "独立站点" },
  { id: "relay", label: "API 中转站" },
];

export const SOURCE_INTAKE_COPY = {
  ldxp: {
    fieldLabel: "公开店铺地址",
    placeholder: "https://pay.ldxp.cn/shop/xxxxx",
    hint: "例如 https://wzyp.cn/shop/xxxxx 或 https://pay.ldxp.cn/shop/xxxxx。系统仍会核对实际来源类型。",
  },
  16688: {
    fieldLabel: "16688 店铺地址",
    placeholder: "https://www.16688.com.cn/shop/HARVEY",
    hint: "例如 https://www.16688.com.cn/shop/HARVEY；系统会读取公开店铺商品和真实店铺编号。",
  },
  independent: {
    fieldLabel: "独立站或商品页地址",
    placeholder: "https://shop.example.com/products/example",
    hint: "提交公开店铺首页、商品页面或 JSON Feed 地址。系统自动识别 Dujiao-Next、异次元/ACG-Faka、WooCommerce、Schema.org 等来源并核验商品。",
  },
  relay: {
    fieldLabel: "中转站官网",
    placeholder: "https://relay.example.com",
    hint: "填写公开官网；接口 Base URL 在下方单独填写。",
  },
};

export function isValidPublicSourceUrl(value) {
  try {
    const url = new URL(value);
    const hostname = url.hostname.toLowerCase().replace(/^\[|\]$/g, "");
    const ipv4 = hostname.match(/^\d+(?:\.\d+){3}$/);
    const isPrivateIpv4 = (address) => {
      const parts = address.split(".").map(Number);
      if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) return false;
      const [a, b] = parts;
      return a === 0 || a === 10 || a === 127 || (a === 100 && b >= 64 && b <= 127) || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
    };
    const privateIpv4 = ipv4 && isPrivateIpv4(ipv4[0]);
    const mappedIpv4 = hostname.match(/^::ffff:(\d+(?:\.\d+){3})$/);
    const mappedHex = hostname.match(/^::ffff:([0-9a-f]{1,4}):([0-9a-f]{1,4})$/);
    const mappedAddress = mappedIpv4?.[1] || (mappedHex
      ? `${Number.parseInt(mappedHex[1], 16) >> 8}.${Number.parseInt(mappedHex[1], 16) & 255}.${Number.parseInt(mappedHex[2], 16) >> 8}.${Number.parseInt(mappedHex[2], 16) & 255}`
      : null);
    const privateIpv6 = hostname.includes(":") && (
      hostname === "::" || hostname === "::1" || hostname.startsWith("fc") || hostname.startsWith("fd") || hostname.startsWith("fe80:")
      || (mappedAddress && isPrivateIpv4(mappedAddress))
    );
    return url.protocol === "https:"
      && !url.username
      && !url.password
      && Boolean(hostname)
      && hostname !== "localhost"
      && !privateIpv4
      && !privateIpv6
      && !hostname.endsWith(".local")
      && !hostname.endsWith(".internal");
  } catch {
    return false;
  }
}
