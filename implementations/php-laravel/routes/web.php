<?php

use App\Http\Controllers\BenchmarkController;
use Illuminate\Support\Facades\Route;

Route::get('/health', [BenchmarkController::class, 'health']);
Route::get('/serialize', [BenchmarkController::class, 'serialize']);
Route::get('/users/{id}', [BenchmarkController::class, 'user']);
Route::get('/cpu/{rounds}', [BenchmarkController::class, 'cpu'])->whereNumber('rounds');
Route::get('/aggregate', [BenchmarkController::class, 'aggregate']);
