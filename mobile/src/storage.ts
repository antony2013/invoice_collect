import AsyncStorage from "@react-native-async-storage/async-storage";
import { User } from "./types";

const KEY_TOKEN = "auth_token";
const KEY_USER = "auth_user";
const KEY_URL = "api_base_url";

export async function saveToken(token: string) {
  await AsyncStorage.setItem(KEY_TOKEN, token);
}

export async function loadToken(): Promise<string | null> {
  return AsyncStorage.getItem(KEY_TOKEN);
}

export async function clearToken() {
  await AsyncStorage.removeItem(KEY_TOKEN);
}

export async function saveUser(user: User) {
  await AsyncStorage.setItem(KEY_USER, JSON.stringify(user));
}

export async function loadUser(): Promise<User | null> {
  const raw = await AsyncStorage.getItem(KEY_USER);
  return raw ? JSON.parse(raw) : null;
}

export async function clearUser() {
  await AsyncStorage.removeItem(KEY_USER);
}

export async function saveUrl(url: string) {
  await AsyncStorage.setItem(KEY_URL, url);
}

export async function loadUrl(): Promise<string | null> {
  return AsyncStorage.getItem(KEY_URL);
}
