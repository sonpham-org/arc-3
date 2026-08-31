"""a060 Balance Pole -- countersteer an unstable load while the cart advances."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,ARENA,RAIL,CART,POLE,LOAD,CENTER,GOAL,MOTION,BAD=4,8,9,12,14,10,13,11,6,15
LEVELS=[
 {"name":"Counter Left","seq":(1,)},{"name":"Counter Right","seq":(1,2)},
 {"name":"Catch Lean","seq":(1,3,2)},{"name":"Advance Slowly","seq":(4,1,2,3,4)},
 {"name":"Shared Control","seq":(4,1,3,2,4,1,2)},{"name":"Balance Pole","seq":(1,3,2,4,1,2,3,4,2,1)},
]
def advance(s,a):
 cart,lean,velocity,progress,stable,history,snapshot=s
 force={1:-1,2:1,3:0,4:1}.get(a,0)
 if a in (1,2,3,4):
  velocity=max(-2,min(2,velocity+force+(1 if lean>0 else -1 if lean<0 else 0)));lean=max(-5,min(5,lean+velocity-force));cart=max(0,min(10,cart+force));progress=min(8,progress+int(a==4 and abs(lean)<=2));stable=min(6,stable+1) if abs(lean)<=1 else 0;history=(history+(lean,))[-8:]
 elif a==5:snapshot=(cart,lean,velocity,progress,stable,history)
 return cart,lean,velocity,progress,stable,history,snapshot
for x in LEVELS:
 s=(5,1,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARENA;f[47:53,6:58]=RAIL
  x=8+g.cart*4;f[41:50,x:x+11]=CART;cx=x+5;topx=max(6,min(57,cx+g.lean*3))
  steps=max(1,abs(36-12));
  for i in range(steps+1):xx=cx+(topx-cx)*i//steps;yy=40-(28*i//steps);f[yy:yy+3,xx:xx+3]=POLE
  f[8:16,topx-3:topx+5]=LOAD;f[7:18,29:35]=CENTER
  f[54:58,7:7+g.progress*6]=GOAL
  for i,v in enumerate(g.history[-8:]):f[23:26,9+i*6:14+i*6]=MOTION if abs(v)<=1 else BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A060(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a060",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cart,self.lean,self.velocity,self.progress,self.stable,self.history,self.snapshot=(5,1,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cart,self.lean,self.velocity,self.progress,self.stable,self.history,self.snapshot=advance((self.cart,self.lean,self.velocity,self.progress,self.stable,self.history,self.snapshot),a)
  elif a==6:
   if (self.cart,self.lean,self.velocity,self.progress,self.stable,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
