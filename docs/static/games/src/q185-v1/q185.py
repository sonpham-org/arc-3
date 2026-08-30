"""q185 Promise Tokens -- temporary help creates identity-bound future obligations."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,HELPER,TOKEN,DECLINE,REPAY,CURSOR,BAD=1,10,9,14,8,6,12,13
LEVELS=[
 {"name":"One Promise","offers":[0],"accept":[1]}, {"name":"Named Debt","offers":[0,1],"accept":[1,0]},
 {"name":"Two Helpers","offers":[1,0,2],"accept":[1,1,0]}, {"name":"Delayed Obligation","offers":[2,0,1,2],"accept":[0,1,1,1]},
 {"name":"Identity Ledger","offers":[0,2,1,0,2],"accept":[1,0,1,1,1]}, {"name":"Promise Tokens","offers":[2,0,1,2,1,0],"accept":[1,1,0,1,1,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=HALL
  for i,h in enumerate(g.offers):x=7+i*8;f[14:23,x:x+6]=HELPER+h;f[27:33,x:x+6]=TOKEN if i<g.stage and g.accept[i] else DECLINE
  for i,h in enumerate(g.debts):x=9+i*10;f[41:48,x:x+8]=REPAY+h;f[50:53,x:x+8]=CURSOR if i==g.cursor else HALL
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q185(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.offers=self.accept=[];self.stage=0;self.debts=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q185",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.offers=list(s["offers"]);self.accept=list(s["accept"]);self.stage=0;self.debts=[];self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if self.stage<len(self.offers) and a in (1,2):
   yes=a==1
   if yes!=bool(self.accept[self.stage]):self.failed=True;self.lose()
   else:
    if yes:self.debts.append(self.offers[self.stage])
    self.stage+=1
  elif self.stage==len(self.offers) and a==3:self.cursor=(self.cursor-1)%len(self.debts)
  elif self.stage==len(self.offers) and a==4:self.cursor=(self.cursor+1)%len(self.debts)
  elif self.stage==len(self.offers) and a==5 and self.debts:self.debts.pop(self.cursor);self.cursor=0 if not self.debts else self.cursor%len(self.debts)
  elif self.stage==len(self.offers) and a==6:
   if not self.debts:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
