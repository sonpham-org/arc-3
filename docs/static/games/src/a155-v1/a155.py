"""a155 Exception Ladder -- apply the most specific matching category rule."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LEDGER,OBJECT,BASE,EXCEPTION,EXCEPTION_TWO,CURSOR,ACCEPT,REJECT,ERROR=6,8,7,12,14,10,13,4,11,9
BAD=15
LEVELS=[
 {"name":"Apply Base Rule","seq":(1,)},{"name":"Select Object","seq":(2,)},
 {"name":"Add Exception","seq":(3,1)},{"name":"Choose Specific Rule","seq":(1,2,3,4,2)},
 {"name":"Exception to Exception","seq":(1,3,2,1,4,3,2)},{"name":"Exception Ladder","seq":(1,2,3,1,4,2,3,1,4,3)},
]
FEATURES=(0,1,2,3,4,5)
def advance(s,a):
 classes,cursor,depth,correct,errors,history,snapshot=s;c=list(classes)
 if a==1:c[cursor]=1-c[cursor];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:depth=(depth+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  truth=[int((f%2==0)^(f>=3)^(depth==2 and f==5)) for f in FEATURES];correct=sum(int(c[i]==truth[i]) for i in range(6));errors=6-correct;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(c),cursor,depth,correct,errors,history)
 return tuple(c),cursor,depth,correct,errors,history,snapshot
for q in LEVELS:
 s=((1,0,1,0,1,0),0,0,4,2,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LEDGER;cols=(BASE,EXCEPTION,EXCEPTION_TWO)
  for i,v in enumerate(g.classes):
   x=9+(i%3)*17;y=14+(i//3)*20;f[y:y+14,x:x+14]=OBJECT;f[y+3:y+11,x+3:x+11]=ACCEPT if v else REJECT
   if i==g.cursor:f[y-3:y,x:x+14]=CURSOR
  for i in range(3):f[7:10,8+i*16:20+i*16]=cols[i] if i<=g.depth else LEDGER
  f[54:58,8:8+g.correct*7]=ACCEPT;f[54:58,50:50+g.errors*2]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A155(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a155",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.classes,self.cursor,self.depth,self.correct,self.errors,self.history,self.snapshot=((1,0,1,0,1,0),0,0,4,2,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.classes,self.cursor,self.depth,self.correct,self.errors,self.history,self.snapshot=advance((self.classes,self.cursor,self.depth,self.correct,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.classes,self.cursor,self.depth,self.correct,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
