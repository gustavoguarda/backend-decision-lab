<?php

namespace App\Http\Controllers;

use GuzzleHttp\Client as GuzzleClient;
use GuzzleHttp\Promise\Utils;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;

class BenchmarkController extends Controller
{
    /**
     * One Guzzle client persisted for the life of the Octane worker. A fresh
     * client (or Http::pool) per request rebuilds curl handles each time, which
     * churns connections under a concurrent fan-out and drops calls; a shared
     * client keeps keep-alive connections in its handle pool across requests.
     */
    private static ?GuzzleClient $guzzle = null;

    private static function guzzle(): GuzzleClient
    {
        if (self::$guzzle === null) {
            self::$guzzle = new GuzzleClient([
                'timeout' => 10,
                'curl' => [CURLOPT_TCP_KEEPALIVE => 1],
            ]);
        }

        return self::$guzzle;
    }

    public function health(): JsonResponse
    {
        return response()->json(['status' => 'ok']);
    }

    public function serialize(): JsonResponse
    {
        return response()->json([
            'id' => 123,
            'name' => 'John Doe',
            'email' => 'john@example.com',
        ]);
    }

    public function user(string $id): JsonResponse
    {
        $row = DB::selectOne(
            'SELECT id, name, email, created_at FROM users WHERE id = ?',
            [(int) $id]
        );

        if ($row === null) {
            return response()->json(['error' => 'not found'], 404);
        }

        return response()->json([
            'id' => (int) $row->id,
            'name' => $row->name,
            'email' => $row->email,
            'created_at' => $this->toIso8601($row->created_at),
        ]);
    }

    public function cpu(string $rounds): JsonResponse
    {
        if (! is_numeric($rounds) || (int) $rounds <= 0) {
            return response()->json(['error' => 'not found'], 404);
        }

        $rounds = (int) $rounds;
        if ($rounds > 10000000) {
            $rounds = 10000000;
        }

        $h = hash('sha256', 'backend-decision-lab', true);
        for ($i = 1; $i < $rounds; $i++) {
            $h = hash('sha256', $h, true);
        }

        return response()->json([
            'rounds' => $rounds,
            'hash' => bin2hex($h),
        ]);
    }

    public function aggregate(): JsonResponse
    {
        $url = env('UPSTREAM_URL', 'http://upstream:8080').'/delay/0.05';
        $client = self::guzzle();

        $start = microtime(true);

        // Fire all 10 concurrently via async promises, then wait for them to settle.
        $promises = [];
        for ($i = 0; $i < 10; $i++) {
            $promises[] = $client->getAsync($url);
        }
        $results = Utils::settle($promises)->wait();

        $tookMs = (int) round((microtime(true) - $start) * 1000);

        $succeeded = 0;
        foreach ($results as $result) {
            if (($result['state'] ?? null) === 'fulfilled'
                && $result['value']->getStatusCode() === 200) {
                $succeeded++;
            }
        }

        return response()->json([
            'requests' => 10,
            'succeeded' => $succeeded,
            'took_ms' => $tookMs,
        ]);
    }

    private function toIso8601(string $value): string
    {
        // created_at comes back as a Postgres timestamptz string; normalize to ISO-8601.
        return \Carbon\Carbon::parse($value)->toIso8601String();
    }
}
