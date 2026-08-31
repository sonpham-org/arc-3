"""a141 Reversible Scrambler -- build a universally invertible token network."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,NETWORK,WIRE,GATE_SWAP,GATE_CONTROL,GATE_MERGE,TOKEN,CURSOR,PRESERVED,LOST=7,8,9,12,14,6,10,13,4,11
BAD=15
LEVELS=[
 {"name":"Change Gate","seq":(1,)},{"name":"Select Gate","seq":(2,)},
 {"name":"Probe Token","seq":(3,1)},{"name":"Test Backward","seq":(1,2,3,4,2)},
 {"name":"Preserve Information","seq":(1,3,2,1,4,3,2)},{"name":"Reversible Scrambler","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 gates,cursor,probe,preserved,reversed_,loss,history,snapshot=s;g=list(gates)
 if a==1:g[cursor]=(g[cursor]+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%5;history=(history+(2,))[-8:]
 elif a==3:probe=(probe+1)%4;history=(history+(3,))[-8:]
 elif a==4:loss=g.count(2);preserved=5-loss;reversed_=int(loss==0);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(g),cursor,probe,preserved,reversed_,loss,history)
 return tuple(g),cursor,probe,preserved,reversed_,loss,history,snapshot
for q in LEVELS:
 s=((0,1,0,1,0),0,0,5,1,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=NETWORK;cols=(GATE_SWAP,GATE_CONTROL,GATE_MERGE)
  for lane in range(4):f[13+lane*11:16+lane*11,7:57]=WIRE;f[12+lane*11:18+lane*11,8:13]=TOKEN
  for i,v in enumerate(g.gates):
   x=16+i*8;y=19+(i%2)*16;f[y:y+12,x:x+7]=cols[v]
   if i==g.cursor:f[y-3:y,x:x+7]=CURSOR
  f[54:58,8:8+g.preserved*8]=PRESERVED;f[7:10,8:8+g.loss*10]=LOST
  if g.bad:f[1:4,18:46]=BAD
  return f
class A141(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a141",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.gates,self.cursor,self.probe,self.preserved,self.reversed,self.loss,self.history,self.snapshot=((0,1,0,1,0),0,0,5,1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.gates,self.cursor,self.probe,self.preserved,self.reversed,self.loss,self.history,self.snapshot=advance((self.gates,self.cursor,self.probe,self.preserved,self.reversed,self.loss,self.history,self.snapshot),a)
  elif a==6:
   if (self.gates,self.cursor,self.probe,self.preserved,self.reversed,self.loss,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
