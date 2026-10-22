import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ROOT_PATH } from "@/routes";

/**
 * 未找到页面。
 */
export function NotFound(): JSX.Element {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div>
        <h1 className="text-2xl font-semibold">页面不存在</h1>
        <p className="mt-2 text-sm text-muted-foreground">当前访问的 QianKun 页面无法匹配。</p>
      </div>
      <Button asChild>
        <Link to={ROOT_PATH}>返回概览</Link>
      </Button>
    </div>
  );
}
