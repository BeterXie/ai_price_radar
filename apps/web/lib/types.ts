export type ProductCard = {
  slug: string;
  platform: string;
  display_name: string;
  subtitle: string;
  product_type: string;
  lowest_price: string | null;
  offer_count: number;
  in_stock_count: number;
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
  goods_type: string;
  price: string | null;
  market_price: string | null;
  currency: string;
  stock_count: number | null;
  stock_status: string;
  auto_delivery: boolean | null;
  tags: string[];
  risk_flags: string[];
  source_url: string;
  first_seen_at: string;
  last_seen_at: string;
  observed_at: string;
};

export type ProductDetail = ProductCard & {
  description: string;
  offers: Offer[];
  history: { observed_at: string; price: string | null; stock_status: string }[];
};

export type OfferPage = {
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
  offer_count: number;
  offers: Offer[];
};

export type Meta = {
  platforms: string[];
  product_types: string[];
  tags: string[];
};
