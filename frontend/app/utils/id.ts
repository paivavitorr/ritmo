import { v7 } from 'uuid'

/** Gera um UUIDv7 (ordenável por tempo) no cliente, para entidades e mutações. */
export function novoId(): string {
  return v7()
}
