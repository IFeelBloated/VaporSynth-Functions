import vapoursynth as vs
import math

class Dither (object):

      def __init__(self):
          self.core = vs.get_core ()
          self.std  = self.core.std
          self.n2s  = self.core.fmtc.nativetostack16
          self.s2n  = self.core.fmtc.stack16tonative
          self.Expr = self.std.Expr

      def get_msb (self, src, native=True):
          if native == True:
              clip  =  self.n2s (src)
          else:
              clip  = src
          return self.std.CropRel (clip, 0, 0, 0, (clip.height // 2))
          
      def get_lsb (self, src, native=True):
          if native == True:
              clip  =  self.n2s (src)
          else:
              clip  = src
          return self.std.CropRel (clip, 0, 0, (clip.height // 2), 0)

      def add16 (self, src1, src2, dif=True):
          if dif == True:
              clip = self.std.MergeDiff (src1, src2)
          else:
              clip = self.Expr ([src1, src2], ["x y +"])
          return clip
          
      def sub16 (self, src1, src2, dif=True):
          if dif == True:
             clip = self.std.MakeDiff (src1, src2)
          else:
             clip = self.Expr ([src1, src2], ["x y -"])
          return clip
          
      def max_dif16 (self, src1, src2, ref):
          clip = self.Expr ([src1, src2, ref], ["x z - abs y z - abs > x y ?"])
          return clip
          
      def min_dif16 (self, src1, src2, ref):
          clip = self.Expr ([src1, src2, ref], ["x z - abs y z - abs > y x ?"])
          return clip

      def merge16 (self, src1, src2, mask):
          clip = self.Expr ([src1, src2, mask], ["65536 z - x * z y * + 32768 + 65536 /"])
          return clip

      def merge16_8 (self, src1, src2, mask):
          maskS  = self.std.StackVertical([mask, mask])
          mask16 = self.s2n (maskS)
          clip   = self.Expr ([src1, src2, mask16], ["65536 z - x * z y * + 32768 + 65536 /"])
          return clip
          
      def build_sigmoid_expr (self, string, inv=False, thr=0.5, cont=6.5):
          x0v = 1 / (1 + math.exp (cont * thr))
          x1v = 1 / (1 + math.exp (cont * (thr - 1)))
          
          x0   = repr (x0v)
          x1m0 = repr (x1v - x0v)
          cont = repr (cont)
          thr  = repr (thr)
          
          if inv == True:
             expr = thr + " 1 " + string + " " + x1m0 + " * " + x0 + " + 0.000001 max / 1 - 0.000001 max log " + cont + " / -"
          else:
             expr = "1 1 " + cont + " " + thr + " " + string + " - * exp + / " + x0 + " - " + x1m0 + " /"
          return (expr)
          
      def sigmoid_direct (self, src, thr=0.5, cont=6.5):
          expr = "x 65536 /"
          expr = self.build_sigmoid_expr (expr, False, thr, cont)
          expr = expr + " 65536 *"
          clip = self.Expr ([src], expr)
          return clip

      def sigmoid_inverse (self, src, thr=0.5, cont=6.5):
          expr = "x 65536 /"
          expr = self.build_sigmoid_expr (expr, True, thr, cont)
          expr = expr + " 65536 *"
          clip = self.Expr ([src], expr)
          return clip

      def linear_and_gamma (self, src, l2g_flag=True, tv_range_in=False, tv_range_out=False, curve="srgb", gcor=1.0, sigmoid=False, thr=0.5, cont=6.5):
          if curve == "srgb":
              k0    = "0.04045"
              phi   = "12.92"
              alpha = "0.055"
              gamma = "2.4"
          elif curve == "709":
              k0    = "0.081"
              phi   = "4.5"
              alpha = "0.099"
              gamma = "2.22222"
          elif curve == "240":
              k0    = "0.0912"
              phi   = "4.0"
              alpha = "0.1115"
              gamma = "2.22222"
          elif curve == "2020":
              k0    = "0.08145"
              phi   = "4.5"
              alpha = "0.0993"
              gamma = "2.22222"
          else:
              k0    = "0.04045"
              phi   = "12.92"
              alpha = "0.055"
              gamma = "2.4"

          if tv_range_in == True:
           expr = "x 4096 - 56064 /"
          else:
           expr = "x 65536 /"
              
            g2l = expr
            g2l = g2l + " " + k0 +" <= " + g2l + " " + phi +" / " + g2l + " " + alpha + " + 1 " + alpha + " + / log " + gamma + " * exp   ?"
          
          if gcor != 1.0:
            g2l = g2l + " 0 >=   " + g2l + " log " + repr (gcor) + " * exp   " + g2l + "   ?" 
          else:
            g2l = g2l

          if sigmoid == True:
            g2l = self.build_sigmoid_expr (g2l , True , thr, cont)
          else:
            g2l = g2l
              
          if sigmoid == True:
            l2g = self.build_sigmoid_expr (expr , False , thr, cont)
          else:
            l2g = expr
              
          if gcor != 1.0:
            l2g = l2g + " 0 >=   " + l2g + " log " + repr (gcor) + " * exp   " + l2g + "   ?"
          else:
            l2g = l2g
              
            l2g =   l2g + " " + k0 + " " + phi + " / <= " + l2g + " " + phi + " * " + l2g + " log 1 " + gamma + " / * exp " + alpha + " 1 + * " + alpha + " -   ?"
          
          if l2g_flag == True:
           expr = l2g
          else:
           expr = g2l
              
          if tv_range_out == True:
           expr = expr + " 56064 * 4096 +"
          else:
           expr = expr + " 65536 *"
              
          clip  = self.Expr ([src], expr)
          return clip
          
      def gamma_to_linear (self, src, tv_range_in=False, tv_range_out=False, curve="srgb", gcor=1.0, sigmoid=False, thr=0.5, cont=6.5):
          clip  = self.linear_and_gamma (src, False, tv_range_in, tv_range_out, curve, gcor, sigmoid, thr, cont)
          return clip
          
      def linear_to_gamma (self, src, tv_range_in=False, tv_range_out=False, curve="srgb", gcor=1.0, sigmoid=False, thr=0.5, cont=6.5):
          clip  = self.linear_and_gamma (src, True, tv_range_in, tv_range_out, curve, gcor, sigmoid, thr, cont)
          return clip

      def limit_dif16 (self, flt, src, ref, thr=0.25, elast=3.0):
          thr   = thr * 256
          alpha = repr (1 / (thr * (elast - 1)))
          beta  = repr (elast * thr)
          clip  = self.Expr ([flt, src, ref], ["x z - abs " + repr (thr) + " <= x x z - abs " + beta + " >= ? y y " + alpha + " x y - * " + beta + " x y - abs - * + ?"])
          return clip 
