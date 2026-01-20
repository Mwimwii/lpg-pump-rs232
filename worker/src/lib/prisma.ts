import { PrismaClient } from '@prisma/client/edge';
import { withAccelerate } from '@prisma/extension-accelerate';

let prismaInstance: PrismaClient;

export function getPrismaClient(databaseUrl: string) {
  if (!prismaInstance) {
    prismaInstance = new PrismaClient({
      datasources: {
        db: {
          url: databaseUrl,
        },
      },
    }).$extends(withAccelerate());
  }
  return prismaInstance;
}