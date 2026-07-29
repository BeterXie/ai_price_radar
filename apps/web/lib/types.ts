export type ProductCard = {
  slug: string;
  platform: string;
  display_name: string;
  subtitle: string;
  product_type: string;
  lowest_price: string | null;
  related_lowest_price: string | null;
  offer_count: number;
  in_stock_count: number;
  comparable_offer_count: number;
  trusted_offer_count: number;
  median_price: string | null;
  last_updated_at: string | null;
  tags: string[];
};

export type Offer = {
  id: number;
  shop_token: string;
  shop_name: string;
  original_name: string;
  original_category: string;
  original_description: string;
  description_available: boolean;
  goods_type: string;
  price: string | null;
  market_price: string | null;
  currency: string;
  stock_count: number | null;
  stock_status: string;
  auto_delivery: boolean | null;
  tags: string[];
  risk_flags: string[];
  delivery_type: string;
  is_comparable: boolean;
  service_period: string;
  warranty: string;
  use_scenarios: string[];
  item_fingerprint: string;
  low_price_warning: string | null;
  is_trusted_price: boolean;
  source_url: string;
  first_seen_at: string;
  last_seen_at: string;
  observed_at: string;
};

export type ProductDetail = ProductCard & {
  description: string;
  highest_price: string | null;
  offer_group_count: number;
  price_breakdown: DeliveryPriceSummary[];
  snapshot_id: number | null;
  snapshot_at: string | null;
  offers: Offer[];
  offer_groups: OfferGroup[];
  history: { observed_at: string; price: string | null; stock_status: string }[];
};

export type DeliveryPriceSummary = {
  delivery_type: string;
  lowest_price: string | null;
  offer_count: number;
  in_stock_count: number;
};

export type OfferGroup = {
  product_slug: string;
  product_name: string;
  fingerprint: string;
  representative: Offer;
  offer_count: number;
  shop_count: number;
  in_stock_count: number;
  lowest_price: string | null;
  highest_price: string | null;
  latest_observed_at: string | null;
};

export type OfferPage = {
  items: Offer[];
};

export type OfferGroupPage = {
  items: OfferGroup[];
  total: number;
  offer_total: number;
  snapshot_id: number | null;
};

export type CatalogOfferGroupPage = OfferGroupPage & {
  in_stock_count: number;
  last_updated_at: string | null;
  snapshot_at: string | null;
};

export type GroupOffers = {
  items: Offer[];
};

export type ShopDetail = {
  token: string;
  name: string;
  source_url: string;
  platform: string;
  status: string;
  first_seen_at: string;
  last_success_at: string | null;
  last_seen_at: string | null;
  consecutive_failures: number;
  offer_count: number;
  offers: Offer[];
};

export type Meta = {
  platforms: string[];
  product_types: string[];
  tags: string[];
};

export type CatalogResponse = {
  items: ProductCard[];
  total: number;
  offer_count: number;
  in_stock_count: number;
  snapshot_id: number | null;
  snapshot_at: string | null;
};
