"""a130 Leader Tile -- break ring symmetry using an off-ring landmark."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,ARENA,AGENT,PULSE_A,PULSE_B,LANDMARK,CURSOR,LEADER,MULTIPLE,NONE=12,8,9,10,14,13,11,4,6,7
BAD=15
LEVELS=[
 {"name":"Change Signal","seq":(1,)},{"name":"Select Agent","seq":(2,)},
 {"name":"Move Landmark","seq":(3,1)},{"name":"Compare Pulses","seq":(1,2,3,4,2)},
 {"name":"Elect One","seq":(1,3,2,1,4,3,2)},{"name":"Leader Tile","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 rules,cursor,landmark,leaders,winner,history,snapshot=s;r=list(rules)
 if a==1:r[cursor]=(r[cursor]+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:landmark=(landmark+1)%8;history=(history+(3,))[-8:]
 elif a==4:
  scores=[r[i]*3-min((i-landmark)%8,(landmark-i)%8) for i in range(8)];top=max(scores);leaders=scores.count(top);winner=scores.index(top) if leaders==1 else -1;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(r),cursor,landmark,leaders,winner,history)
 return tuple(r),cursor,landmark,leaders,winner,history,snapshot
for q in LEVELS:
 s=((0,1,2,0,1,2,0,1),0,0,2,-1,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARENA;pts=((31,9),(46,15),(53,31),(46,47),(31,54),(16,47),(9,31),(16,15))
  for i,(x,y) in enumerate(pts):
   f[y-4:y+5,x-4:x+5]=LEADER if i==g.winner else AGENT;f[y-2:y+3,x-2:x+3]=PULSE_A if g.rules[i]==0 else PULSE_B
   if i==g.cursor:f[y-7:y-5,x-5:x+6]=CURSOR
  lx,ly=pts[g.landmark];lx=31+(lx-31)*6//5;ly=31+(ly-31)*6//5;f[max(0,ly-4):min(64,ly+5),max(0,lx-4):min(64,lx+5)]=LANDMARK
  col=LEADER if g.leaders==1 else NONE if g.leaders==0 else MULTIPLE;f[54:58,8:8+g.leaders*8]=col
  if g.bad:f[1:4,18:46]=BAD
  return f
class A130(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a130",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.rules,self.cursor,self.landmark,self.leaders,self.winner,self.history,self.snapshot=((0,1,2,0,1,2,0,1),0,0,2,-1,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.rules,self.cursor,self.landmark,self.leaders,self.winner,self.history,self.snapshot=advance((self.rules,self.cursor,self.landmark,self.leaders,self.winner,self.history,self.snapshot),a)
  elif a==6:
   if (self.rules,self.cursor,self.landmark,self.leaders,self.winner,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
