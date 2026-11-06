#include "slang/IR/SlangDialect.h"
#include "slang/Transforms/Passes.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/SCF/IR/SCF.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"
#include "mlir/IR/PatternMatch.h"
#include "mlir/Pass/Pass.h"

using namespace mlir;

namespace {
struct LowerSimulateGravity : OpRewritePattern<slang::SimulateGravityOp> {
  using OpRewritePattern::OpRewritePattern;
  LogicalResult matchAndRewrite(slang::SimulateGravityOp op, PatternRewriter &rewriter) const override {
    Location loc = op.getLoc();
    Value x0 = op.getX(), v0 = op.getV(), mass = op.getMass();
    Value G = op.getGravity(), dt = op.getDt(), steps = op.getSteps();
    auto f64 = rewriter.getF64Type();
    auto index = rewriter.getIndexType();
    Value one = rewriter.create<arith::ConstantIndexOp>(loc, 1);
    auto loop = rewriter.create<scf::ForOp>(loc, rewriter.create<arith::ConstantIndexOp>(loc, 0), steps, one,
                                           ValueRange{x0, v0});
    {
      OpBuilder::InsertionGuard guard(rewriter);
      rewriter.setInsertionPointToStart(loop.getBody());
      Value x = loop.getRegionIterArgs()[0];
      Value v = loop.getRegionIterArgs()[1];
      Value xx = rewriter.create<arith::MulFOp>(loc, x, x);
      Value gm = rewriter.create<arith::MulFOp>(loc, G, mass);
      Value acc = rewriter.create<arith::DivFOp>(loc, gm, xx);
      Value dv = rewriter.create<arith::MulFOp>(loc, acc, dt);
      Value vn = rewriter.create<arith::AddFOp>(loc, v, dv);
      Value dx = rewriter.create<arith::MulFOp>(loc, vn, dt);
      Value xn = rewriter.create<arith::AddFOp>(loc, x, dx);
      rewriter.create<scf::YieldOp>(loc, ValueRange{xn, vn});
    }
    rewriter.replaceOp(op, loop.getResults());
    return success();
  }
};


struct LowerExecutionRegion : OpRewritePattern<slang::ExecutionRegionOp> {
  using OpRewritePattern::OpRewritePattern;
  LogicalResult matchAndRewrite(slang::ExecutionRegionOp op, PatternRewriter &rewriter) const override {
    // Region metadata has already been materialized structurally by the
    // producer. Remove only the metadata marker; never change its mode.
    rewriter.eraseOp(op);
    return success();
  }
};

template <typename OpTy>
struct LowerSemanticToken : OpRewritePattern<OpTy> {
  using OpRewritePattern<OpTy>::OpRewritePattern;
  LogicalResult matchAndRewrite(OpTy op, PatternRewriter &rewriter) const override {
    Location loc = op.getLoc();
    // The token carries compile-time semantic metadata but does not yet carry
    // a runtime collection ABI.  Lowering it to an i64 constant preserves the
    // fact that this stage is a planning/result-token lowering rather than a
    // claim that collection data has already been materialized.
    Value zero = rewriter.create<arith::ConstantIntOp>(loc, 0, 64);
    rewriter.replaceOp(op, zero);
    return success();
  }
};

struct LowerSlangPass : PassWrapper<LowerSlangPass, OperationPass<ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(LowerSlangPass)
  StringRef getArgument() const final { return "lower-slang"; }
  StringRef getDescription() const final { return "Lower S-Lang high-level operations to standard MLIR"; }
  void runOnOperation() override {
    RewritePatternSet patterns(&getContext());
    patterns.add<LowerSimulateGravity>(&getContext());
    patterns.add<LowerExecutionRegion>(&getContext());
    patterns.add<LowerSemanticToken<slang::FilterOp>>(&getContext());
    patterns.add<LowerSemanticToken<slang::MapOp>>(&getContext());
    patterns.add<LowerSemanticToken<slang::SortOp>>(&getContext());
    patterns.add<LowerSemanticToken<slang::AggregateOp>>(&getContext());
    patterns.add<LowerSemanticToken<slang::ReduceOp>>(&getContext());
    patterns.add<LowerSemanticToken<slang::SequenceOp>>(&getContext());
    patterns.add<LowerSemanticToken<slang::ChooseOp>>(&getContext());
    patterns.add<LowerSemanticToken<slang::FindPathOp>>(&getContext());
    patterns.add<LowerSemanticToken<slang::SatisfyOp>>(&getContext());
    ConversionTarget target(getContext());
    target.addLegalDialect<arith::ArithDialect, scf::SCFDialect, func::FuncDialect, memref::MemRefDialect>();
    target.addLegalOp<ModuleOp>();
    target.addIllegalOp<slang::ExecutionRegionOp>();
    target.addIllegalOp<slang::SimulateGravityOp>();
    target.addIllegalOp<slang::FilterOp>();
    target.addIllegalOp<slang::MapOp>();
    target.addIllegalOp<slang::SortOp>();
    target.addIllegalOp<slang::AggregateOp>();
    target.addIllegalOp<slang::ReduceOp>();
    target.addIllegalOp<slang::SequenceOp>();
    target.addIllegalOp<slang::ChooseOp>();
    target.addIllegalOp<slang::FindPathOp>();
    target.addIllegalOp<slang::SatisfyOp>();
    if (failed(applyPartialConversion(getOperation(), target, std::move(patterns)))) signalPassFailure();
  }
};
}

namespace slang { void registerSlangPasses() { PassRegistration<LowerSlangPass>(); } }
