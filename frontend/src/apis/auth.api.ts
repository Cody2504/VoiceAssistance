import axios from "axios";
import { ROUTES } from "@/constants/routes";

export async function getMe() {
  const r = await axios.get(ROUTES.ME);
  return r.data?.data;
}
