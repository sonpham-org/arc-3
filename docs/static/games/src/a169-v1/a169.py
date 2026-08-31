"""a169 Same Future -- merge visually different states with identical action responses."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,MACHINE,STATE_A,STATE_B,BIN_A,BIN_B,PROBE,CURSOR,CORRECT,ERROR=5,8,12,14,10,13,9,11,4,6
BAD=15
BEHAVIOR=(0,1,0,2,1,2,0,1)
LEVELS=[
 {"name":"Move State Bin","seq":(1,)},{"name":"Select State","seq":(2,)},
 {"name":"Probe Action","seq":(3,1)},{"name":"Compare Futures","seq":(1,2,3,4,2)},
 {"name":"Merge Appearances","seq":(1,3,2,1,4,3,2)},{"name":"Same Future","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 bins,cursor,probe,correct,errors,history,snapshot=s;b=list(bins)
 if a==1:b[cursor]=(b[cursor]+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:probe=(probe+1)%4;history=(history+(3,))[-8:]
 elif a==4:correct=sum(int(b[i]==BEHAVIOR[i]) for i in range(8));errors=8-correct;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(b),cursor,probe,correct,errors,history)
 return tuple(b),cursor,probe,correct,errors,history,snapshot
for q in LEVELS:
 s=((0,1,0,2,1,2,0,1),0,0,8,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MACHINE;cols=(BIN_A,BIN_B,PROBE)
  for i,v in enumerate(g.bins):
   x=9+(i%4)*13;y=13+(i//4)*22;f[y:y+16,x:x+11]=STATE_A if i%2==0 else STATE_B;f[y+5:y+11,x+3:x+8]=cols[v]
   if i==g.cursor:f[y-3:y,x:x+11]=CURSOR
  f[54:58,8:8+g.correct*6]=CORRECT;f[7:10,8:8+g.errors*6]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A169(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a169",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins,self.cursor,self.probe,self.correct,self.errors,self.history,self.snapshot=((0,1,0,2,1,2,0,1),0,0,8,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.cursor,self.probe,self.correct,self.errors,self.history,self.snapshot=advance((self.bins,self.cursor,self.probe,self.correct,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.bins,self.cursor,self.probe,self.correct,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
