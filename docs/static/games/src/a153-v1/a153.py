"""a153 Family Resemblance -- classify by overlapping prototype features."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,SORTER,OBJECT_A,OBJECT_B,FEATURE_A,FEATURE_B,ROUTE_IN,ROUTE_OUT,CURSOR,SCORE=4,8,12,14,10,13,9,7,11,6
BAD=15
FEATURES=(0b1110,0b1101,0b1011,0b0111,0b1001,0b0011)
LEVELS=[
 {"name":"Route Object","seq":(1,)},{"name":"Select Object","seq":(2,)},
 {"name":"Shift Prototype","seq":(3,1)},{"name":"Count Shared Features","seq":(1,2,3,4,2)},
 {"name":"Reject One-feature Rule","seq":(1,3,2,1,4,3,2)},{"name":"Family Resemblance","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 routed,cursor,prototype,score,false_routes,history,snapshot=s
 if a==1:routed^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:prototype=((prototype<<1)|(prototype>>3))&15;history=(history+(3,))[-8:]
 elif a==4:positive=[(FEATURES[i]&prototype).bit_count()>=2 for i in range(6)];score=sum(int(bool((routed>>i)&1)==positive[i]) for i in range(6));false_routes=6-score;history=(history+(4,))[-8:]
 elif a==5:snapshot=(routed,cursor,prototype,score,false_routes,history)
 return routed,cursor,prototype,score,false_routes,history,snapshot
for q in LEVELS:
 s=(0b001111,0,0b1110,4,2,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SORTER
  for i,bits in enumerate(FEATURES):
   x=9+(i%3)*17;y=12+(i//3)*22;f[y:y+15,x:x+14]=OBJECT_A if (g.routed>>i)&1 else OBJECT_B
   for k in range(4):f[y+3+k*2:y+5+k*2,x+3:x+11]=FEATURE_A if (bits>>k)&1 else FEATURE_B
   if i==g.cursor:f[y-3:y,x:x+14]=CURSOR
  f[54:58,8:8+g.score*7]=SCORE;f[7:10,8:8+g.false_routes*7]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A153(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a153",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.routed,self.cursor,self.prototype,self.score,self.false_routes,self.history,self.snapshot=(0b001111,0,0b1110,4,2,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.routed,self.cursor,self.prototype,self.score,self.false_routes,self.history,self.snapshot=advance((self.routed,self.cursor,self.prototype,self.score,self.false_routes,self.history,self.snapshot),a)
  elif a==6:
   if (self.routed,self.cursor,self.prototype,self.score,self.false_routes,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
