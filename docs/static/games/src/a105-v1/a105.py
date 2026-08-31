"""a105 Exact Cover Mosaic -- cover every target cell once with anchored patches."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,BOARD,TARGET,PATCH_A,PATCH_B,PATCH_C,OVERLAP,HOLE,ANCHOR,BAD=1,8,9,12,14,10,15,4,13,6
SHAPES=((0,1),(1,2,5),(0,3,4))
LEVELS=[
 {"name":"Place Patch","seq":(1,)},{"name":"Select Patch","seq":(3,)},
 {"name":"Rotate Patch","seq":(2,1)},{"name":"Avoid Overlap","seq":(1,3,2,1,4)},
 {"name":"Mandatory Anchor","seq":(2,1,3,1,4,3,1)},{"name":"Exact Cover Mosaic","seq":(1,3,2,1,4,3,1,2,4,1)},
]
def advance(s,a):
 coverage,cursor,rotation,placed,overlap,holes,history,snapshot=s;cv=list(coverage);rot=list(rotation);pl=list(placed)
 if a==1:
  pl[cursor]^=1
  for cell in SHAPES[cursor]:idx=(cell+rot[cursor])%9;cv[idx]+=1 if pl[cursor] else -1
  history=(history+(1,))[-8:]
 elif a==2:
  if pl[cursor]:
   for cell in SHAPES[cursor]:cv[(cell+rot[cursor])%9]-=1
  rot[cursor]=(rot[cursor]+1)%4
  if pl[cursor]:
   for cell in SHAPES[cursor]:cv[(cell+rot[cursor])%9]+=1
  history=(history+(2,))[-8:]
 elif a==3:cursor=(cursor+1)%3;history=(history+(3,))[-8:]
 elif a==4:overlap=sum(int(x>1) for x in cv);holes=sum(int(x==0) for x in cv);history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(cv),cursor,tuple(rot),tuple(pl),overlap,holes,history)
 return tuple(cv),cursor,tuple(rot),tuple(pl),overlap,holes,history,snapshot
for x in LEVELS:
 s=((0,0,0,0,0,0,0,0,0),0,(0,0,0),(0,0,0),0,9,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BOARD;cols=(PATCH_A,PATCH_B,PATCH_C)
  for i,v in enumerate(g.coverage):x=13+(i%3)*14;y=13+(i//3)*14;f[y:y+12,x:x+12]=OVERLAP if v>1 else cols[i%3] if v==1 else TARGET
  f[9:12,13+g.cursor*14:25+g.cursor*14]=ANCHOR
  f[53:57,8:8+g.overlap*7]=BAD;f[57:60,8:8+g.holes*5]=HOLE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A105(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a105",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.coverage,self.cursor,self.rotation,self.placed,self.overlap,self.holes,self.history,self.snapshot=((0,0,0,0,0,0,0,0,0),0,(0,0,0),(0,0,0),0,9,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.coverage,self.cursor,self.rotation,self.placed,self.overlap,self.holes,self.history,self.snapshot=advance((self.coverage,self.cursor,self.rotation,self.placed,self.overlap,self.holes,self.history,self.snapshot),a)
  elif a==6:
   if (self.coverage,self.cursor,self.rotation,self.placed,self.overlap,self.holes,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
